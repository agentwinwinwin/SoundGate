import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from devices.command_transport import publish_payload
from devices.device_protocol import FILE_RAW_CHUNK_BYTES, build_command, build_file_chunk
from devices.models import FileTransfer, TerminalCommand
from devices.onenet import OneNETError


class Command(BaseCommand):
    help = '发送排队的终端扩展命令和WAV文件分片；终端ACK由run_onenet_listener处理'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--interval', type=float, default=0.5)

    def handle(self, *args, **options):
        while True:
            self.process_commands()
            self.process_transfers()
            if options['once']: return
            time.sleep(max(0.1, options['interval']))

    def process_commands(self):
        cutoff = timezone.now() - timedelta(seconds=settings.ONENET_COMMAND_TIMEOUT_SECONDS)
        queryset = TerminalCommand.objects.filter(
            Q(status=TerminalCommand.Status.QUEUED) | Q(status=TerminalCommand.Status.SENT, updated_at__lt=cutoff)
        )[:20]
        for command in queryset:
            if command.attempts >= settings.ONENET_COMMAND_MAX_RETRIES:
                command.status = TerminalCommand.Status.FAILED; command.error = '等待终端ACK超时'
                command.save(update_fields=['status', 'error', 'updated_at']); continue
            try:
                result = publish_payload(command.device, command.payload)
                command.status = TerminalCommand.Status.SENT
                command.response = result
                command.attempts += 1
                command.save(update_fields=['status', 'response', 'attempts', 'updated_at'])
            except OneNETError as exc:
                command.attempts += 1
                command.error = str(exc)
                if command.attempts >= settings.ONENET_COMMAND_MAX_RETRIES:
                    command.status = TerminalCommand.Status.FAILED
                command.save(update_fields=['status', 'attempts', 'error', 'updated_at'])

    def process_transfers(self):
        active = FileTransfer.objects.filter(status__in=[FileTransfer.Status.QUEUED, FileTransfer.Status.TRANSFERRING, FileTransfer.Status.VERIFYING])[:5]
        for transfer in active:
            try:
                self.send_transfer_step(transfer)
            except (OneNETError, OSError) as exc:
                transfer.attempts += 1; transfer.error = str(exc)
                if transfer.attempts >= settings.ONENET_COMMAND_MAX_RETRIES: transfer.status = FileTransfer.Status.FAILED
                transfer.save(update_fields=['status', 'attempts', 'error', 'updated_at'])

    def send_transfer_step(self, transfer):
        if transfer.status == FileTransfer.Status.QUEUED:
            payload = build_command('fb', transfer.transfer_id, k=transfer.audio_file.kind, s=transfer.audio_file.size, n=transfer.total_chunks, c=transfer.audio_file.crc32)
            publish_payload(transfer.device, payload)
            transfer.status = FileTransfer.Status.TRANSFERRING
            transfer.awaiting_chunk = -1
            transfer.attempts = 1
        elif transfer.status == FileTransfer.Status.TRANSFERRING:
            if transfer.awaiting_chunk is not None:
                if timezone.now() - transfer.updated_at < timedelta(seconds=settings.ONENET_COMMAND_TIMEOUT_SECONDS): return
                if transfer.attempts >= settings.ONENET_COMMAND_MAX_RETRIES:
                    transfer.status = FileTransfer.Status.FAILED; transfer.error = '等待终端分片ACK超时'
                    transfer.save(update_fields=['status', 'error', 'updated_at']); return
                if transfer.awaiting_chunk == -1:
                    payload = build_command('fb', transfer.transfer_id, k=transfer.audio_file.kind, s=transfer.audio_file.size, n=transfer.total_chunks, c=transfer.audio_file.crc32)
                else:
                    with transfer.audio_file.file.open('rb') as source:
                        source.seek(transfer.awaiting_chunk * FILE_RAW_CHUNK_BYTES); chunk = source.read(FILE_RAW_CHUNK_BYTES)
                    payload = build_file_chunk(transfer.transfer_id, transfer.awaiting_chunk, chunk)
                publish_payload(transfer.device, payload); transfer.attempts += 1
                transfer.save(update_fields=['attempts', 'updated_at']); return
            with transfer.audio_file.file.open('rb') as source:
                source.seek(transfer.next_chunk * FILE_RAW_CHUNK_BYTES)
                chunk = source.read(FILE_RAW_CHUNK_BYTES)
            if chunk:
                publish_payload(transfer.device, build_file_chunk(transfer.transfer_id, transfer.next_chunk, chunk))
                transfer.awaiting_chunk = transfer.next_chunk; transfer.attempts = 1
            else:
                publish_payload(transfer.device, build_command('fe', transfer.transfer_id))
                transfer.status = FileTransfer.Status.VERIFYING
                transfer.awaiting_chunk = transfer.total_chunks; transfer.attempts = 1
        elif transfer.status == FileTransfer.Status.VERIFYING:
            if timezone.now() - transfer.updated_at < timedelta(seconds=settings.ONENET_COMMAND_TIMEOUT_SECONDS):
                return
            if transfer.attempts >= settings.ONENET_COMMAND_MAX_RETRIES:
                transfer.status = FileTransfer.Status.FAILED
                transfer.error = '等待终端文件校验ACK超时'
            else:
                publish_payload(transfer.device, build_command('fe', transfer.transfer_id))
                transfer.attempts += 1
        transfer.save(update_fields=['status', 'awaiting_chunk', 'attempts', 'error', 'updated_at'])
