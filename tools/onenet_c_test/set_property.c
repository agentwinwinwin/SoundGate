#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct response_buffer {
    char *data;
    size_t length;
};

static size_t collect_response(void *contents, size_t size, size_t count, void *context)
{
    size_t bytes = size * count;
    struct response_buffer *buffer = context;
    char *next = realloc(buffer->data, buffer->length + bytes + 1);
    if (next == NULL) return 0;
    buffer->data = next;
    memcpy(buffer->data + buffer->length, contents, bytes);
    buffer->length += bytes;
    buffer->data[buffer->length] = '\0';
    return bytes;
}

int main(int argc, char **argv)
{
    const char *token = getenv("ONENET_DEVICE_TOKEN");
    const char *product = getenv("ONENET_PRODUCT_ID");
    const char *device = argc > 1 ? argv[1] : "device-b";
    int volume = argc > 2 ? atoi(argv[2]) : 6;
    char payload[256];
    char auth_header[512];
    struct response_buffer response = {calloc(1, 1), 0};
    CURL *curl;
    CURLcode result;
    long status = 0;

    if (token == NULL || token[0] == '\0') {
        fprintf(stderr, "ONENET_DEVICE_TOKEN is not configured\n");
        return 2;
    }
    if (product == NULL || product[0] == '\0') {
        fprintf(stderr, "ONENET_PRODUCT_ID is not configured\n");
        return 2;
    }
    if (volume < 0 || volume > 9) {
        fprintf(stderr, "volume must be between 0 and 9\n");
        return 2;
    }

    snprintf(payload, sizeof(payload),
        "{\"product_id\":\"%s\",\"device_name\":\"%s\","
        "\"params\":{\"DftVolume\":%d}}", product, device, volume);
    snprintf(auth_header, sizeof(auth_header), "Authorization: %s", token);

    curl_global_init(CURL_GLOBAL_DEFAULT);
    curl = curl_easy_init();
    if (curl == NULL) return 2;

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, auth_header);
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(curl, CURLOPT_URL,
        "https://iot-api.heclouds.com/thingmodel/set-device-property");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, (long)strlen(payload));
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, collect_response);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

    printf("request=%s\nrequest_bytes=%zu\n", payload, strlen(payload));
    result = curl_easy_perform(curl);
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    printf("http_status=%ld\n", status);
    if (result != CURLE_OK) {
        printf("curl_error=%s\n", curl_easy_strerror(result));
    } else {
        printf("response=%s\n", response.data);
    }

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    curl_global_cleanup();
    free(response.data);
    return result == CURLE_OK ? 0 : 1;
}
