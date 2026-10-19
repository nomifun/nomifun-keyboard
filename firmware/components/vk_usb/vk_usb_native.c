/* NomiFun native keyboard protocol v1. Four-key/status serial TX owner and one ordered
 * queue for key events and policy receipts. No update/flash or legacy product ABI. */
#include "vk_usb.h"
#include "vk_usb_json.h"
#include "vk_input.h"
#include "nk_screen.h"

#include <stdatomic.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#ifdef NK_NATIVE_TEST
#include "nk_native_platform.h"
#else
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#endif

#define FRAME_MAX 768U
#define TX_CAPACITY 16U
#define LEASE_MS 5000U
typedef struct { uint32_t epoch; uint16_t length; uint8_t bytes[FRAME_MAX]; } tx_t;
typedef struct { uint32_t generation; vk_input_transition_t value; } nk_key_t;
static QueueHandle_t s_tx, s_keys;
static atomic_uint s_epoch, s_generation, s_release_generation, s_policy_generation;
static atomic_uint s_faults, s_retired_faults;
static atomic_bool s_tx_busy;
typedef struct { uint8_t bytes[1024]; size_t count; bool retiring; } rx_t;
static uint32_t s_last_epoch, s_last_request;
static bool s_last_screen_available;
static uint8_t s_last_command[512];
static size_t s_last_command_length;

static uint64_t s_lease;
static char s_id[32], s_cached[384];
static vk_usb_json_document_t s_json;
static const int s_gpio[] = {0,18,17,16};

static uint64_t now_ms(void) { return (uint64_t)esp_timer_get_time()/1000U; }
static uint32_t nonzero_next(uint32_t x) { ++x; return x == 0U ? 1U : x; }
static bool faulted(void)
{
    unsigned faults=atomic_load(&s_faults);
    return faults==UINT_MAX||faults!=atomic_load(&s_retired_faults);
}
static void mark_fault(uint32_t origin_epoch)
{
    unsigned faults=atomic_load(&s_faults);
    while(faults!=UINT_MAX&&!atomic_compare_exchange_weak(&s_faults,&faults,faults+1U)){}
    /* If the owner already retired this published fault, its delayed CAS
     * cannot close a later epoch without a new fault. A fault first published
     * late still requires conservative retirement of the current connection. */
    if(origin_epoch!=0U)(void)atomic_compare_exchange_strong(&s_epoch,&origin_epoch,0U);
}
static bool queue_frame(tx_t *frame)
{
    if (faulted() || frame->epoch == 0U || frame->epoch != atomic_load(&s_epoch)) return false;
    if (xQueueSend(s_tx,frame,pdMS_TO_TICKS(100U)) == pdTRUE) return true;
    mark_fault(frame->epoch); return false;
}
static bool json_send(const char *json)
{
    tx_t frame={.epoch=atomic_load(&s_epoch)};
    size_t n=strlen(json); if(n>FRAME_MAX-4U)return false;
    frame.length=(uint16_t)(n+4U);frame.bytes[0]=1U;frame.bytes[1]=0x10U;
    frame.bytes[2]=(uint8_t)n;frame.bytes[3]=(uint8_t)(n>>8U);
    memcpy(frame.bytes+4U,json,n);return queue_frame(&frame);
}
static void error(uint32_t request,const char *code)
{
    char json[192];snprintf(json,sizeof(json),"{\"event\":\"nk_error\",\"epoch\":%lu,\"request_id\":%lu,\"code\":\"%s\"}",(unsigned long)atomic_load(&s_epoch),(unsigned long)request,code);(void)json_send(json);
}
static void reset_gestures(void)
{
    atomic_store(&s_policy_generation,0U);
    atomic_store(&s_generation,nonzero_next(atomic_load(&s_generation)));
    xQueueReset(s_keys);
}
static void close_epoch(void)
{
    /* Close key admission before retiring the epoch and its queued receipts. */
    uint32_t previous=atomic_exchange(&s_epoch,0U);
    if(nk_screen_available())(void)nk_screen_apply(NK_SLEEPING);
    reset_gestures();xQueueReset(s_tx);
    uint64_t deadline=now_ms()+300U;
    while(atomic_load(&s_tx_busy)&&now_ms()<deadline)vTaskDelay(pdMS_TO_TICKS(1U));
    if(atomic_load(&s_tx_busy))mark_fault(previous);
    s_last_request=0U;s_last_command_length=0U;s_cached[0]='\0';
}
static void transmit(const tx_t *tx)
{
    atomic_store(&s_tx_busy,true);
    if(tx->epoch!=atomic_load(&s_epoch)||faulted()){atomic_store(&s_tx_busy,false);return;}
    size_t offset=0U;uint64_t deadline=now_ms()+250U;
    while(offset<tx->length&&now_ms()<deadline){
        if(tx->epoch!=atomic_load(&s_epoch)||faulted())break;
        int written=usb_serial_jtag_write_bytes(tx->bytes+offset,tx->length-offset,pdMS_TO_TICKS(20U));
        if(written<0||written>(int)(tx->length-offset))break;
        if(written>0)offset+=(size_t)written;
    }
    if(offset!=tx->length)mark_fault(tx->epoch);
    atomic_store(&s_tx_busy,false);
}
static void tx_task(void *unused)
{
    (void)unused;tx_t tx;
    for(;;){
        if(xQueueReceive(s_tx,&tx,portMAX_DELAY)!=pdTRUE)continue;
        transmit(&tx);
    }
}
typedef struct { vk_input_debounce_t input; uint32_t generation; unsigned release_samples; } scanner_t;
static void scan_keys(scanner_t *state,uint8_t pressed,uint32_t now)
{
        uint32_t current=atomic_load(&s_generation);
        if(state->generation!=current){vk_input_debounce_reset(&state->input);state->generation=current;state->release_samples=0U;}
        if(pressed==0U){if(state->release_samples<2U)++state->release_samples;if(state->release_samples==2U)atomic_store(&s_release_generation,current);}else state->release_samples=0U;
        vk_input_transition_t values[8];size_t count=vk_input_debounce_sample(&state->input,pressed,now,values,8U);
        uint32_t epoch=atomic_load(&s_epoch);
        if(count>8U)mark_fault(epoch);
        else if(epoch!=0U&&!faulted())for(size_t i=0;i<count&&!faulted();i++){
            nk_key_t key={.generation=current,.value=values[i]};
            if(xQueueSend(s_keys,&key,0U)!=pdTRUE)mark_fault(epoch);
        }
}
static void scanner_task(void *unused)
{
    (void)unused;scanner_t state={0};
    for(;;){
        uint8_t pressed=0U;for(unsigned i=0;i<4U;i++)if(gpio_get_level(s_gpio[i])==0)pressed|=(uint8_t)(1U<<i);
        scan_keys(&state,pressed,(uint32_t)now_ms());
        vTaskDelay(pdMS_TO_TICKS(5U));
    }
}
static void send_button(vk_input_transition_t value)
{
    static const char *names[]={"button_down","button_up","button_click"};
    char json[256];
    snprintf(json,sizeof(json),"{\"event\":\"%s\",\"epoch\":%lu,\"button\":\"k%u\",\"duration_ms\":%lu}",names[value.kind],(unsigned long)atomic_load(&s_epoch),(unsigned)value.key+1U,(unsigned long)value.duration_ms);
    (void)json_send(json);
}
static void key_event(nk_key_t key)
{
    if(faulted()||key.generation!=atomic_load(&s_generation)||key.generation!=atomic_load(&s_release_generation)||key.generation!=atomic_load(&s_policy_generation))return;
    if(key.value.kind==VK_INPUT_TRANSITION_DOWN)nk_screen_key((unsigned)key.value.key);
    send_button(key.value);
}
static uint16_t member(const char *key){return vk_usb_json_object_find(&s_json,vk_usb_json_root(&s_json),key);}
static bool number(const char *key,uint32_t *value){return vk_usb_json_uint32(&s_json,member(key),UINT32_MAX,true,value)==VK_USB_JSON_OK;}
static bool exact(const char *const *keys,size_t n){return vk_usb_json_object_exact_keys(&s_json,vk_usb_json_root(&s_json),keys,n);}
static void info(void)
{
    char json[640];uint32_t epoch=atomic_load(&s_epoch);s_last_screen_available=nk_screen_available();const char *reason=s_last_screen_available?"":",\"reason\":\"driver_unavailable\"";
    snprintf(json,sizeof(json),"{\"event\":\"device_info\",\"hardware\":\"vibe_keyboard\",\"firmware_version\":\"0.3-screen.2\",\"device_id\":\"%s\",\"buttons\":[\"k1\",\"k2\",\"k3\",\"k4\"],\"native_keyboard_protocol\":1,\"epoch\":%lu}",s_id,(unsigned long)epoch);(void)json_send(json);
    snprintf(json,sizeof(json),"{\"event\":\"nk_capabilities\",\"protocol\":1,\"epoch\":%lu,\"firmware_build\":\"nomifun-native-0.3-screen.2\",\"policy_ack\":true,\"wait_release\":true,\"audio_source\":\"system\",\"key_events\":[\"button_down\",\"button_up\",\"button_click\"],\"display\":{\"version\":1,\"available\":%s%s,\"width\":428,\"height\":142,\"privacy\":\"status_only\"}}",(unsigned long)epoch,nk_screen_available()?"true":"false",reason);(void)json_send(json);
}
static void command(const uint8_t *bytes,size_t length)
{
    char event[32];uint32_t epoch=0U,request=0U;
    if(vk_usb_json_parse(&s_json,bytes,length)!=VK_USB_JSON_OK||vk_usb_json_string_copy(&s_json,member("event"),event,sizeof(event))!=VK_USB_JSON_OK){error(0U,"invalid_request");return;}
    if(strcmp(event,"transport")==0){
        const char *keys[]={"event","kind"};if(!exact(keys,2U)||!vk_usb_json_string_equal(&s_json,member("kind"),"usb"))return;
        close_epoch();if(faulted())return;
        if(usb_serial_jtag_wait_tx_done(pdMS_TO_TICKS(20U))!=ESP_OK){mark_fault(0U);return;}
        s_last_epoch=nonzero_next(s_last_epoch);atomic_store(&s_epoch,s_last_epoch);
        if(faulted()){uint32_t opened=s_last_epoch;(void)atomic_compare_exchange_strong(&s_epoch,&opened,0U);return;}
        s_lease=now_ms()+LEASE_MS;return;
    }
    if(atomic_load(&s_epoch)==0U)return;
    if(strcmp(event,"get_device_info")==0){const char *keys[]={"event"};if(exact(keys,1U))info();return;}
    if(strcmp(event,"ping")==0){const char *keys[]={"event"};if(exact(keys,1U))s_lease=now_ms()+LEASE_MS;return;}
    if(!number("request_id",&request)||!number("epoch",&epoch)||epoch!=atomic_load(&s_epoch)){error(request,"wrong_epoch");return;}
    /* Monotone IDs make delayed/repeated commands harmless within one epoch. */
    if(request==s_last_request){if(length!=s_last_command_length||memcmp(bytes,s_last_command,length)!=0)error(request,"request_conflict");else if(s_cached[0]!='\0')(void)json_send(s_cached);return;}
    if(request<s_last_request){error(request,"stale_request");return;}
    if(strcmp(event,"nk_policy")==0){
        const char *keys[]={"event","epoch","request_id","voice_key"};char name[5];
        if(!exact(keys,4U)||vk_usb_json_string_copy(&s_json,member("voice_key"),name,sizeof(name))!=VK_USB_JSON_OK){error(request,"invalid_request");return;}
        if(strcmp(name,"none")!=0){error(request,"invalid_request");return;}
        reset_gestures();
        atomic_store(&s_policy_generation,atomic_load(&s_generation));
        snprintf(s_cached,sizeof(s_cached),"{\"event\":\"nk_policy_applied\",\"epoch\":%lu,\"request_id\":%lu,\"session_id\":0,\"voice_key\":\"none\",\"capture_stopped\":true,\"waiting_release\":true}",(unsigned long)epoch,(unsigned long)request);
    }else if(strcmp(event,"nk_display")==0){
        const char *keys[]={"event","epoch","request_id","state"};char state_name[20];nk_screen_state_t state;
        if(!exact(keys,4U)||vk_usb_json_string_copy(&s_json,member("state"),state_name,sizeof(state_name))!=VK_USB_JSON_OK||!nk_screen_parse(state_name,&state)){error(request,"invalid_request");return;}
        if(nk_screen_apply(state)!=ESP_OK){error(request,"display_unavailable");return;}
        snprintf(s_cached,sizeof(s_cached),"{\"event\":\"nk_display_applied\",\"epoch\":%lu,\"request_id\":%lu,\"state\":\"%s\",\"applied\":true,\"frames\":%lu,\"backlight_on\":%s,\"pwm_duty\":%lu,\"buffer_bytes\":6848,\"visual_verified\":false}",(unsigned long)epoch,(unsigned long)request,state_name,(unsigned long)nk_screen_frames(),nk_screen_backlight()?"true":"false",(unsigned long)nk_screen_duty());
    }else{error(request,"unsupported_command");return;}
    s_last_request=request;s_last_command_length=length;memcpy(s_last_command,bytes,length);(void)json_send(s_cached);
}
static bool retire_fault(rx_t *rx)
{
    if(!faulted())return true;
    if(!rx->retiring){rx->retiring=true;rx->count=0U;close_epoch();}
    unsigned observed=atomic_load(&s_faults);
    if(observed==UINT_MAX||atomic_load(&s_tx_busy))return false;
    /* A stopped TX task alone does not prove that IDF's TX ring is empty. */
    if(usb_serial_jtag_wait_tx_done(pdMS_TO_TICKS(20U))!=ESP_OK)return false;
    uint8_t stale[256];bool quiet=false;
    for(unsigned reads=0;reads<16U;reads++){
        int n=usb_serial_jtag_read_bytes(stale,sizeof(stale),0U);
        if(n<0)return false;
        if(n==0){quiet=true;break;}
    }
    if(!quiet)return false;
    rx->count=0U;
    /* Only this owner retires the observed fault. A concurrent producer's
     * later sequence remains unequal, so a new fault cannot be overwritten. */
    atomic_store(&s_retired_faults,observed);
    rx->retiring=false;
    return false; /* Even successful retirement requires a later transport. */
}
static void owner_step(rx_t *rx)
{
        if(!retire_fault(rx)){vTaskDelay(pdMS_TO_TICKS(10U));return;}
        if(atomic_load(&s_epoch)!=0U&&now_ms()>s_lease){close_epoch();rx->count=0U;}
        int n=usb_serial_jtag_read_bytes(rx->bytes+rx->count,sizeof(rx->bytes)-rx->count,pdMS_TO_TICKS(5U));
        if(n<0){mark_fault(atomic_load(&s_epoch));return;}
        if(n>0)rx->count+=(size_t)n;
        size_t offset=0U;
        while(rx->count-offset>=4U&&!faulted()){
            uint8_t *p=rx->bytes+offset;size_t body=(size_t)p[2]+((size_t)p[3]<<8U);
            if(p[0]!=1U||p[1]!=0x10U||body>512U){++offset;continue;}
            if(rx->count-offset<body+4U)break;
            command(p+4U,body);offset+=body+4U;
        }
        if(offset!=0U){memmove(rx->bytes,rx->bytes+offset,rx->count-offset);rx->count-=offset;}
        if(atomic_load(&s_epoch)!=0U&&s_last_screen_available!=nk_screen_available())info();
        nk_key_t key;while(!faulted()&&xQueueReceive(s_keys,&key,0U)==pdTRUE)key_event(key);
}
static void owner_task(void *unused)
{
    (void)unused;rx_t rx={0};
    for(;;)owner_step(&rx);
}
esp_err_t vk_usb_start(void)
{
    s_tx=xQueueCreate(TX_CAPACITY,sizeof(tx_t));s_keys=xQueueCreate(32U,sizeof(nk_key_t));
    if(s_tx==NULL||s_keys==NULL)return ESP_ERR_NO_MEM;
    uint8_t mac[6];esp_err_t e=esp_read_mac(mac,ESP_MAC_WIFI_STA);if(e!=ESP_OK)return e;
    snprintf(s_id,sizeof(s_id),"NK-%02X%02X%02X%02X%02X%02X",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    gpio_config_t gpio={.pin_bit_mask=(1ULL<<0)|(1ULL<<18)|(1ULL<<17)|(1ULL<<16),.mode=GPIO_MODE_INPUT,.pull_up_en=GPIO_PULLUP_ENABLE};
    e=gpio_config(&gpio);if(e!=ESP_OK)return e;
    usb_serial_jtag_driver_config_t config=USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();config.rx_buffer_size=2048U;config.tx_buffer_size=4096U;
    e=usb_serial_jtag_driver_install(&config);if(e!=ESP_OK)return e;
    atomic_store(&s_generation,1U);
    if(xTaskCreate(tx_task,"nk_tx",4096U,NULL,8U,NULL)!=pdPASS||xTaskCreate(scanner_task,"nk_keys",4096U,NULL,7U,NULL)!=pdPASS||xTaskCreate(owner_task,"nk_owner",8192U,NULL,6U,NULL)!=pdPASS){mark_fault(0U);return ESP_ERR_NO_MEM;}
    return ESP_OK;
}



