#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef void *QueueHandle_t;
typedef unsigned TickType_t;
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY UINT32_MAX
#define pdMS_TO_TICKS(x) (x)
#define GPIO_MODE_INPUT 1
#define GPIO_PULLUP_ENABLE 1
#define ESP_MAC_WIFI_STA 1
typedef struct { uint64_t pin_bit_mask; int mode; int pull_up_en; } gpio_config_t;
typedef struct { size_t rx_buffer_size; size_t tx_buffer_size; } usb_serial_jtag_driver_config_t;
#define USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT() ((usb_serial_jtag_driver_config_t){0})
QueueHandle_t xQueueCreate(unsigned,size_t);
int xQueueSend(QueueHandle_t,const void *,unsigned);
int xQueueReceive(QueueHandle_t,void *,unsigned);
void xQueueReset(QueueHandle_t);
void vTaskDelay(unsigned);
int xTaskCreate(void (*)(void *),const char *,unsigned,void *,unsigned,void *);
int gpio_get_level(int);
int gpio_config(const gpio_config_t *);
int usb_serial_jtag_write_bytes(const void *,size_t,unsigned);
int usb_serial_jtag_wait_tx_done(unsigned);
int usb_serial_jtag_read_bytes(void *,size_t,unsigned);
int usb_serial_jtag_driver_install(const usb_serial_jtag_driver_config_t *);
int esp_read_mac(uint8_t *,int);
int64_t esp_timer_get_time(void);
