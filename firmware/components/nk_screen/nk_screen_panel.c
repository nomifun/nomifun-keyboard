/* NV3007 init table and wiring from zerob13/vibe-keyboard commit
 * 019cfa099c2cb3b8d7b9aad665dbc4fd4a09096a (MIT). No LVGL/assets runtime. */
#include "nk_screen.h"
#include <stdatomic.h>
#include <stdlib.h>
#ifdef NK_SCREEN_NATIVE_TEST
#include "nk_screen_native_platform.h"
#else
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "driver/ledc.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#endif
typedef struct {uint8_t command;uint8_t data[4];uint8_t length;uint16_t delay_ms;} init_command_t;
static const init_command_t init[]={
#include "nv3007_init.inc"
};
_Static_assert(sizeof(init)/sizeof(init[0])==119U,"fixed NV3007 sequence");
static spi_device_handle_t s_spi;
static uint16_t *s_pixels;

static atomic_bool s_available,s_backlight;
static atomic_int s_state=NK_CONNECTING,s_key=-1;
static atomic_uint s_request=1U,s_rendered,s_frames,s_key_at;
static uint32_t milliseconds(void){return (uint32_t)(esp_timer_get_time()/1000);}
static esp_err_t transaction(const void *data,size_t length,bool more){spi_transaction_t t={.length=length*8U,.tx_buffer=data,.flags=more?SPI_TRANS_CS_KEEP_ACTIVE:0};return spi_device_polling_transmit(s_spi,&t);}
static esp_err_t command(uint8_t cmd,const uint8_t *data,size_t length){
 esp_err_t e=spi_device_acquire_bus(s_spi,portMAX_DELAY);if(e!=ESP_OK)return e;
 e=gpio_set_level(13,0);if(e==ESP_OK)e=transaction(&cmd,1U,length!=0U);
 if(e==ESP_OK&&length!=0U){e=gpio_set_level(13,1);if(e==ESP_OK)e=transaction(data,length,false);}
 spi_device_release_bus(s_spi);return e;
}
static esp_err_t backlight(unsigned duty){esp_err_t e=ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_0,duty);if(e==ESP_OK)e=ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_0);if(e==ESP_OK)atomic_store(&s_backlight,duty!=0U);return e;}
static esp_err_t flush(nk_screen_state_t state,uint32_t now,int key,uint32_t age){
 const uint8_t x[]={0,0,1,171},y[]={0,14,0,155};
 esp_err_t e=command(0x2a,x,4U);if(e==ESP_OK)e=command(0x2b,y,4U);if(e!=ESP_OK)return e;
 e=spi_device_acquire_bus(s_spi,portMAX_DELAY);if(e!=ESP_OK)return e;
 uint8_t cmd=0x2c;e=gpio_set_level(13,0);if(e==ESP_OK)e=transaction(&cmd,1U,true);if(e==ESP_OK)e=gpio_set_level(13,1);
 for(unsigned row=0;row<NK_SCREEN_HEIGHT&&e==ESP_OK;row+=8U){
  unsigned rows=NK_SCREEN_HEIGHT-row;if(rows>8U)rows=8U;
  nk_screen_render_strip(s_pixels,state,now,key,age,(int)row,(int)rows);
  size_t pixels=rows*NK_SCREEN_WIDTH;
  for(size_t i=0;i<pixels;i++){uint16_t p=s_pixels[i];s_pixels[i]=(uint16_t)((p<<8U)|(p>>8U));}
  e=transaction(s_pixels,pixels*2U,row+rows<NK_SCREEN_HEIGHT);
 }
 spi_device_release_bus(s_spi);if(e==ESP_OK)atomic_fetch_add(&s_frames,1U);return e;
}
static void screen_task(void *unused){
 (void)unused;
 while(atomic_load(&s_available)){
  uint32_t version=atomic_load(&s_request),now=milliseconds();
  nk_screen_state_t state=(nk_screen_state_t)atomic_load(&s_state);
  esp_err_t e=flush(state,now,atomic_load(&s_key),now-atomic_load(&s_key_at));
  if(!atomic_load(&s_available)){(void)backlight(0U);break;}
  if(e==ESP_OK)e=backlight(state==NK_SLEEPING?45U:115U);
  if(e!=ESP_OK){atomic_store(&s_available,false);(void)backlight(0U);break;}
  atomic_store(&s_rendered,version);vTaskDelay(pdMS_TO_TICKS(50U));
 }
 vTaskDelete(NULL);
}
esp_err_t nk_screen_init(void){
 gpio_config_t pins={.pin_bit_mask=(1ULL<<12)|(1ULL<<13),.mode=GPIO_MODE_OUTPUT};esp_err_t e=gpio_config(&pins);if(e!=ESP_OK)return e;
 ledc_timer_config_t timer={.speed_mode=LEDC_LOW_SPEED_MODE,.duty_resolution=LEDC_TIMER_8_BIT,.timer_num=LEDC_TIMER_0,.freq_hz=5000,.clk_cfg=LEDC_AUTO_CLK};e=ledc_timer_config(&timer);if(e!=ESP_OK)return e;
 ledc_channel_config_t light={.gpio_num=9,.speed_mode=LEDC_LOW_SPEED_MODE,.channel=LEDC_CHANNEL_0,.intr_type=LEDC_INTR_DISABLE,.timer_sel=LEDC_TIMER_0,.duty=0};e=ledc_channel_config(&light);if(e!=ESP_OK)return e;
 spi_bus_config_t bus={.mosi_io_num=21,.miso_io_num=-1,.sclk_io_num=14,.quadwp_io_num=-1,.quadhd_io_num=-1,.max_transfer_sz=NK_SCREEN_WIDTH*8*2};e=spi_bus_initialize(SPI2_HOST,&bus,SPI_DMA_CH_AUTO);if(e!=ESP_OK)return e;
 spi_device_interface_config_t device={.clock_speed_hz=40000000,.mode=0,.spics_io_num=11,.queue_size=1,.flags=SPI_DEVICE_HALFDUPLEX};e=spi_bus_add_device(SPI2_HOST,&device,&s_spi);if(e!=ESP_OK)return e;
 e=gpio_set_level(12,0);if(e!=ESP_OK)return e;vTaskDelay(pdMS_TO_TICKS(100U));e=gpio_set_level(12,1);if(e!=ESP_OK)return e;vTaskDelay(pdMS_TO_TICKS(100U));
 for(size_t i=0;i<sizeof(init)/sizeof(init[0]);i++){e=command(init[i].command,init[i].data,init[i].length);if(e!=ESP_OK)return e;if(init[i].delay_ms)vTaskDelay(pdMS_TO_TICKS(init[i].delay_ms));}
 s_pixels=heap_caps_malloc(NK_SCREEN_WIDTH*8U*2U,MALLOC_CAP_DMA);if(!s_pixels)return ESP_ERR_NO_MEM;
 e=flush(NK_CONNECTING,0,-1,1000U);if(e==ESP_OK)e=command(0x29,NULL,0U);if(e==ESP_OK)e=backlight(115U);if(e!=ESP_OK)return e;
 atomic_store(&s_available,true);if(xTaskCreate(screen_task,"nomi_screen",4096U,NULL,2U,NULL)!=pdPASS){atomic_store(&s_available,false);(void)backlight(0U);return ESP_ERR_NO_MEM;}return ESP_OK;
}
bool nk_screen_available(void){return atomic_load(&s_available);}
esp_err_t nk_screen_apply(nk_screen_state_t state){if(state>=NK_STATE_COUNT)return ESP_ERR_INVALID_ARG;if(!nk_screen_available())return ESP_ERR_INVALID_STATE;atomic_store(&s_state,state);uint32_t request=atomic_fetch_add(&s_request,1U)+1U,start=milliseconds();while(nk_screen_available()&&atomic_load(&s_rendered)!=request&&milliseconds()-start<500U)vTaskDelay(pdMS_TO_TICKS(1U));if(nk_screen_available()&&atomic_load(&s_rendered)==request)return ESP_OK;atomic_store(&s_available,false);(void)backlight(0U);return ESP_ERR_TIMEOUT;}
void nk_screen_key(unsigned key){if(key<4U){atomic_store(&s_key,(int)key);atomic_store(&s_key_at,milliseconds());}}
uint32_t nk_screen_frames(void){return atomic_load(&s_frames);}
bool nk_screen_backlight(void){return atomic_load(&s_backlight);}
uint32_t nk_screen_duty(void){return ledc_get_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_0);}


