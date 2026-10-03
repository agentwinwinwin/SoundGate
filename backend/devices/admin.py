from django.contrib import admin
from .models import AudioConfig, Device, ScheduleSlot
@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'name', 'owner', 'online', 'enabled']
    list_filter = ['owner', 'online']
admin.site.register(ScheduleSlot)
admin.site.register(AudioConfig)
