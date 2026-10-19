#pragma once
#include <stdint.h>
#include <stddef.h>
typedef void *spi_device_handle_t;
typedef struct {size_t length;const void *tx_buffer;unsigned flags;} spi_transaction_t;
typedef struct {uint64_t pin_bit_mask;int mode;} gpio_config_t;
typedef struct {int speed_mode,duty_resolution,timer_num,freq_hz,clk_cfg;} ledc_timer_config_t;
typedef struct {int gpio_num,speed_mode,channel,intr_type,timer_sel,duty;} ledc_channel_config_t;
typedef struct {int mosi_io_num,miso_io_num,sclk_io_num,quadwp_io_num,quadhd_io_num,max_transfer_sz;} spi_bus_config_t;
typedef struct {int clock_speed_hz,mode,spics_io_num,queue_size,flags;} spi_device_interface_config_t;
#define pdMS_TO_TICKS(x) (x)
#define pdPASS 1
#define portMAX_DELAY UINT32_MAX
#define SPI_TRANS_CS_KEEP_ACTIVE 1
#define SPI_DEVICE_HALFDUPLEX 1
#define SPI2_HOST 2
#define SPI_DMA_CH_AUTO 1
#define MALLOC_CAP_DMA 1
#define GPIO_MODE_OUTPUT 1
#define LEDC_LOW_SPEED_MODE 0
#define LEDC_CHANNEL_0 0
#define LEDC_TIMER_0 0
#define LEDC_TIMER_8_BIT 8
#define LEDC_AUTO_CLK 0
#define LEDC_INTR_DISABLE 0
int spi_device_polling_transmit(void *,spi_transaction_t *);
int spi_device_acquire_bus(void *,unsigned);
void spi_device_release_bus(void *);
int gpio_set_level(int,int);
int gpio_config(const gpio_config_t *);
int ledc_set_duty(int,int,unsigned);
int ledc_update_duty(int,int);
uint32_t ledc_get_duty(int,int);
int ledc_timer_config(const ledc_timer_config_t *);
int ledc_channel_config(const ledc_channel_config_t *);
int spi_bus_initialize(int,const spi_bus_config_t *,int);
int spi_bus_add_device(int,const spi_device_interface_config_t *,void **);
void *heap_caps_malloc(size_t,unsigned);
int64_t esp_timer_get_time(void);
void vTaskDelay(unsigned);
void vTaskDelete(void *);
int xTaskCreate(void (*)(void *),const char *,unsigned,void *,unsigned,void *);
