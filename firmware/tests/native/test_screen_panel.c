#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define NK_SCREEN_NATIVE_TEST 1
#include "../../components/nk_screen/nk_screen_panel.c"
static unsigned calls,fail_at,display_on,duty,dc,command_count,frames_count;
static unsigned char command_id,window_x[4],window_y[4];
static uint64_t clock_value;
int spi_device_polling_transmit(void *s,spi_transaction_t*t){(void)s;if(++calls==fail_at)return ESP_FAIL;if(dc==0){assert(t->length==8U);command_id=*(const uint8_t*)t->tx_buffer;command_count++;if(command_id==0x29)display_on++;}else if(command_id==0x2a){assert(t->length==32U);memcpy(window_x,t->tx_buffer,4U);}else if(command_id==0x2b){assert(t->length==32U);memcpy(window_y,t->tx_buffer,4U);}else if(command_id==0x2c){assert(t->length<=NK_SCREEN_WIDTH*8U*16U);frames_count++;}return ESP_OK;}
int spi_device_acquire_bus(void*s,unsigned t){(void)s;assert(t==portMAX_DELAY);return ESP_OK;}
void spi_device_release_bus(void*s){(void)s;}
int gpio_set_level(int pin,int level){if(pin==13)dc=(unsigned)level;return ESP_OK;}
int gpio_config(const gpio_config_t*p){assert(p->pin_bit_mask==((1ULL<<12)|(1ULL<<13)));return ESP_OK;}
int ledc_set_duty(int a,int b,unsigned n){(void)a;(void)b;duty=n;if(n!=0U)assert(display_on==1U&&frames_count>=18U);return ESP_OK;}
int ledc_update_duty(int a,int b){(void)a;(void)b;return ESP_OK;}
uint32_t ledc_get_duty(int a,int b){(void)a;(void)b;return duty;}
int ledc_timer_config(const ledc_timer_config_t*p){assert(p->freq_hz==5000);return ESP_OK;}
int ledc_channel_config(const ledc_channel_config_t*p){assert(p->gpio_num==9&&p->duty==0);return ESP_OK;}
int spi_bus_initialize(int h,const spi_bus_config_t*p,int dma){assert(h==SPI2_HOST&&dma==SPI_DMA_CH_AUTO&&p->mosi_io_num==21&&p->sclk_io_num==14);return ESP_OK;}
int spi_bus_add_device(int h,const spi_device_interface_config_t*p,void**out){assert(h==SPI2_HOST&&p->clock_speed_hz==40000000&&p->spics_io_num==11);*out=(void*)1;return ESP_OK;}
void *heap_caps_malloc(size_t n,unsigned c){(void)c;return malloc(n);}
int64_t esp_timer_get_time(void){return (int64_t)clock_value*1000;}
void vTaskDelay(unsigned ms){clock_value+=ms;}
void vTaskDelete(void*p){(void)p;}
int xTaskCreate(void(*fn)(void*),const char*n,unsigned stack,void*p,unsigned priority,void*out){(void)fn;(void)n;(void)stack;(void)p;(void)priority;(void)out;return pdPASS;}
int main(int argc,char**argv){if(argc>1&&strcmp(argv[1],"fail")==0){fail_at=5U;assert(nk_screen_init()==ESP_FAIL&&!nk_screen_available()&&!nk_screen_backlight());puts("panel command failure remains unavailable and dark");return 0;}assert(nk_screen_init()==ESP_OK&&nk_screen_available()&&nk_screen_backlight());assert(command_count==123U&&nk_screen_frames()==1U&&duty==115U);assert(memcmp(window_x,(uint8_t[]){0,0,1,171},4U)==0);assert(memcmp(window_y,(uint8_t[]){0,14,0,155},4U)==0);assert(clock_value>=420U);assert(nk_screen_apply(NK_READY)==ESP_ERR_TIMEOUT&&!nk_screen_available()&&!nk_screen_backlight());puts("panel reset/init119/window/byte-order/full-flush/DISPON/backlight sequence passed");return 0;}

