#include <assert.h>
#include <stdlib.h>
#include <string.h>
#define NK_NATIVE_TEST 1
#include "../../components/vk_usb/vk_usb_native.c"

typedef struct { unsigned cap,head,count;size_t width;uint8_t *data; } fake_queue_t;
static uint64_t clock_ms;
static nk_screen_state_t screen_state;
static uint8_t pending_rx[8192];
static size_t pending_rx_length,tx_quota=SIZE_MAX,wire_bytes;
static bool tx_drained=true,inject_fault_on_drain,rx_failed;
bool nk_screen_available(void){return true;}
esp_err_t nk_screen_apply(nk_screen_state_t state){screen_state=state;return ESP_OK;}
void nk_screen_key(unsigned key){(void)key;}
uint32_t nk_screen_frames(void){return 42U;}
bool nk_screen_backlight(void){return true;}
uint32_t nk_screen_duty(void){return 115U;}
QueueHandle_t xQueueCreate(unsigned cap,size_t width){fake_queue_t*q=calloc(1,sizeof(*q));q->cap=cap;q->width=width;q->data=calloc(cap,width);return q;}
int xQueueSend(QueueHandle_t handle,const void *value,unsigned timeout){(void)timeout;fake_queue_t*q=handle;if(q->count==q->cap)return 0;memcpy(q->data+((q->head+q->count)%q->cap)*q->width,value,q->width);q->count++;return pdTRUE;}
int xQueueReceive(QueueHandle_t handle,void *value,unsigned timeout){(void)timeout;fake_queue_t*q=handle;if(q->count==0U)return 0;memcpy(value,q->data+q->head*q->width,q->width);q->head=(q->head+1U)%q->cap;q->count--;return pdTRUE;}
void xQueueReset(QueueHandle_t handle){fake_queue_t*q=handle;q->head=q->count=0U;}
void vTaskDelay(unsigned ms){clock_ms+=ms;}
int xTaskCreate(void(*fn)(void*),const char*n,unsigned z,void*a,unsigned p,void*h){(void)fn;(void)n;(void)z;(void)a;(void)p;(void)h;return pdPASS;}
int gpio_get_level(int n){(void)n;return 1;}
int gpio_config(const gpio_config_t*c){(void)c;return ESP_OK;}
int usb_serial_jtag_write_bytes(const void*b,size_t n,unsigned t){(void)b;if(tx_quota==0U){clock_ms+=t;return 0;}if(n>tx_quota)n=tx_quota;if(tx_quota!=SIZE_MAX)tx_quota-=n;wire_bytes+=n;return (int)n;}
int usb_serial_jtag_wait_tx_done(unsigned t){(void)t;if(inject_fault_on_drain){inject_fault_on_drain=false;mark_fault(0U);}return tx_drained?ESP_OK:ESP_ERR_TIMEOUT;}
int usb_serial_jtag_read_bytes(void*b,size_t n,unsigned t){(void)t;if(rx_failed)return -1;if(n>pending_rx_length)n=pending_rx_length;memcpy(b,pending_rx,n);memmove(pending_rx,pending_rx+n,pending_rx_length-n);pending_rx_length-=n;return (int)n;}
int usb_serial_jtag_driver_install(const usb_serial_jtag_driver_config_t*c){(void)c;return ESP_OK;}
int esp_read_mac(uint8_t*m,int t){(void)t;memset(m,0x55,6U);return ESP_OK;}
int64_t esp_timer_get_time(void){return (int64_t)clock_ms*1000;}
static void cmd(const char*j){command((const uint8_t*)j,strlen(j));}
static tx_t take(void){tx_t tx;assert(xQueueReceive(s_tx,&tx,0U)==pdTRUE);return tx;}
static void receipt(const char *name)
{
    tx_t tx=take();
    assert(tx.bytes[1]==0x10U);
    char json[FRAME_MAX];
    memcpy(json,tx.bytes+4U,tx.length-4U);
    json[tx.length-4U]='\0';
    assert(strstr(json,name)!=NULL);
    if(strcmp(name,"nk_capabilities")==0){
        assert(strstr(json,"\"protocol\":1")!=NULL);
        assert(strstr(json,"\"audio_source\":\"system\"")!=NULL);
        assert(strstr(json,"\"policy_ack\":true")!=NULL);
        assert(strstr(json,"\"wait_release\":true")!=NULL);
    }
    if(strcmp(name,"nk_policy_applied")==0){
        assert(strstr(json,"\"session_id\":0")!=NULL);
        assert(strstr(json,"\"capture_stopped\":true")!=NULL);
        assert(strstr(json,"\"waiting_release\":true")!=NULL);
    }
}
static void event(unsigned key,vk_input_transition_kind_t kind){nk_key_t value={.generation=atomic_load(&s_generation),.value={.kind=kind,.key=(vk_input_key_t)key}};key_event(value);}
static void feed(const char *json){size_t n=strlen(json);assert(pending_rx_length+n+4U<=sizeof(pending_rx));uint8_t*p=pending_rx+pending_rx_length;p[0]=1U;p[1]=0x10U;p[2]=(uint8_t)n;p[3]=(uint8_t)(n>>8U);memcpy(p+4U,json,n);pending_rx_length+=n+4U;}
static void reopen(rx_t *rx)
{
    assert(!faulted()&&atomic_load(&s_epoch)==0U);
    feed("{\"event\":\"transport\",\"kind\":\"usb\"}");owner_step(rx);
    assert(atomic_load(&s_epoch)!=0U);
    atomic_store(&s_release_generation,atomic_load(&s_generation));
    event(3,VK_INPUT_TRANSITION_DOWN);assert(((fake_queue_t*)s_tx)->count==0U);
    char policy[160];snprintf(policy,sizeof(policy),"{\"event\":\"nk_policy\",\"epoch\":%u,\"request_id\":1,\"voice_key\":\"none\"}",atomic_load(&s_epoch));
    feed(policy);owner_step(rx);receipt("nk_policy_applied");
}
static void recovery_tests(void)
{
    rx_t rx={.count=7U};scanner_t scanner={0};
    const uint32_t old_epoch=atomic_load(&s_epoch),old_generation=atomic_load(&s_generation);
    for(unsigned i=0;i<TX_CAPACITY;i++)assert(json_send("{\"event\":\"pending\"}"));
    assert(!json_send("{\"event\":\"overflow\"}"));assert(faulted()&&atomic_load(&s_epoch)==0U);
    feed("{\"event\":\"transport\",\"kind\":\"usb\"}"); /* queued before retirement: never a fresh handshake */
    atomic_store(&s_tx_busy,true);owner_step(&rx);
    assert(faulted()&&rx.count==0U&&atomic_load(&s_epoch)==0U);
    assert(((fake_queue_t*)s_tx)->count==0U);
    atomic_store(&s_tx_busy,false);tx_drained=false;owner_step(&rx);
    assert(faulted()&&pending_rx_length!=0U); /* task idle is not driver-ring proof */
    tx_drained=true;inject_fault_on_drain=true;owner_step(&rx);
    assert(faulted()&&pending_rx_length==0U); /* newly published fault survived old retirement */
    owner_step(&rx);assert(!faulted()&&atomic_load(&s_epoch)==0U);
    tx_t old={.epoch=old_epoch,.length=4U};size_t before=wire_bytes;transmit(&old);assert(wire_bytes==before);
    reopen(&rx);assert(atomic_load(&s_epoch)!=old_epoch);
    nk_key_t stale={.generation=old_generation,.value={.key=VK_INPUT_KEY_K4,.kind=VK_INPUT_TRANSITION_DOWN}};
    key_event(stale);assert(((fake_queue_t*)s_tx)->count==0U);
    /* A held key across recovery/NONE produces no replay. Only release and
     * a new, debounced press can generate an admitted gesture. */
    scan_keys(&scanner,8U,10U);scan_keys(&scanner,8U,15U);owner_step(&rx);assert(((fake_queue_t*)s_tx)->count==0U);
    scan_keys(&scanner,0U,20U);scan_keys(&scanner,0U,25U);owner_step(&rx);assert(((fake_queue_t*)s_tx)->count==0U);
    scan_keys(&scanner,8U,30U);scan_keys(&scanner,8U,35U);owner_step(&rx);receipt("button_down");
    scan_keys(&scanner,0U,40U);scan_keys(&scanner,0U,45U);owner_step(&rx);receipt("button_up");receipt("button_click");
    /* The actual TX function accepts a prefix, stalls to its deadline, and
     * cannot retire until the driver confirms that prefix has drained. */
    assert(json_send("{\"event\":\"partial\"}"));tx_t partial=take();tx_quota=5U;before=wire_bytes;transmit(&partial);
    assert(wire_bytes==before+5U&&faulted()&&!atomic_load(&s_tx_busy));
    tx_quota=SIZE_MAX;tx_drained=false;owner_step(&rx);assert(faulted());
    tx_drained=true;rx_failed=true;owner_step(&rx);assert(faulted());
    rx_failed=false;owner_step(&rx);assert(!faulted());reopen(&rx);
    /* A full key FIFO reports a transport fault, rather than losing an up
     * and continuing the same epoch. Scanner cannot keep filling it while
     * faulted; the sole owner retires all queued generations. */
    nk_key_t pending={.generation=atomic_load(&s_generation)};
    for(unsigned i=0;i<32U;i++)assert(xQueueSend(s_keys,&pending,0U)==pdTRUE);
    scanner=(scanner_t){0};scan_keys(&scanner,0U,50U);scan_keys(&scanner,0U,55U);
    scan_keys(&scanner,8U,60U);scan_keys(&scanner,8U,65U);assert(faulted());
    unsigned faults=atomic_load(&s_faults);scan_keys(&scanner,0U,70U);scan_keys(&scanner,0U,75U);assert(atomic_load(&s_faults)==faults);
    owner_step(&rx);assert(!faulted()&&((fake_queue_t*)s_keys)->count==0U);reopen(&rx);
    /* In-flight command fragments and queued old transport are discarded.
     * A later fragmented handshake is assembled normally while epoch zero. */
    mark_fault(atomic_load(&s_epoch));rx.count=3U;feed("{\"event\":\"transport\",\"kind\":\"usb\"}");owner_step(&rx);
    assert(!faulted()&&rx.count==0U&&pending_rx_length==0U&&atomic_load(&s_epoch)==0U);
    feed("{\"event\":\"transport\",\"kind\":\"usb\"}");size_t length=pending_rx_length;uint8_t tail[128];assert(length-2U<=sizeof(tail));memcpy(tail,pending_rx+2U,length-2U);
    pending_rx_length=2U;owner_step(&rx);assert(rx.count==2U&&atomic_load(&s_epoch)==0U);
    memcpy(pending_rx,tail,length-2U);pending_rx_length=length-2U;owner_step(&rx);assert(rx.count==0U&&atomic_load(&s_epoch)!=0U);
    /* An old scanner error first published after reopening is not ignored:
     * it conservatively retires the current connection, without automatic
     * admission. No unseen fault is lost to an unconditional boolean clear. */
    uint32_t fresh=atomic_load(&s_epoch);mark_fault(old_epoch);assert(faulted()&&atomic_load(&s_epoch)==fresh);
    owner_step(&rx);assert(!faulted()&&atomic_load(&s_epoch)==0U);reopen(&rx);
    rx_failed=true;owner_step(&rx);assert(faulted()&&atomic_load(&s_epoch)==0U);
    rx_failed=false;owner_step(&rx);assert(!faulted());reopen(&rx);
    atomic_store(&s_faults,UINT_MAX);owner_step(&rx);assert(faulted()&&atomic_load(&s_epoch)==0U);
    puts("overflow/short-write/busy/drain/concurrent-fault/NONE/release recovery tests passed");
}
int main(void)
{
    assert(vk_usb_start()==ESP_OK);
    cmd("{\"event\":\"transport\",\"kind\":\"usb\"}");assert(atomic_load(&s_epoch)==1U);
    cmd("{\"event\":\"get_device_info\"}");receipt("device_info");receipt("nk_capabilities");
    cmd("{\"event\":\"nk_policy\",\"epoch\":1,\"request_id\":1,\"voice_key\":\"none\"}");receipt("nk_policy_applied");
    event(3,VK_INPUT_TRANSITION_DOWN);assert(((fake_queue_t*)s_tx)->count==0U);
    atomic_store(&s_release_generation,atomic_load(&s_generation));
    for(unsigned key=0;key<4U;key++){
        event(key,VK_INPUT_TRANSITION_DOWN);receipt("button_down");
        event(key,VK_INPUT_TRANSITION_UP);receipt("button_up");
        event(key,VK_INPUT_TRANSITION_CLICK);tx_t tx=take();assert(tx.bytes[1]==0x10U);assert(memmem(tx.bytes,tx.length,"button_click",12U)!=NULL);assert(memmem(tx.bytes,tx.length,"session_id",10U)==NULL);
    }
    cmd("{\"event\":\"nk_policy\",\"epoch\":1,\"request_id\":1,\"voice_key\":\"none\"}");receipt("nk_policy_applied");
    cmd("{\"event\":\"nk_policy\",\"epoch\":1,\"request_id\":1,\"voice_key\":\"k4\"}");receipt("request_conflict");
    cmd("{\"event\":\"nk_policy\",\"epoch\":1,\"request_id\":2,\"voice_key\":\"k4\"}");receipt("invalid_request");
    cmd("{\"event\":\"nk_display\",\"epoch\":1,\"request_id\":2,\"state\":\"listening\"}");receipt("nk_display_applied");assert(screen_state==NK_LISTENING);
    cmd("{\"event\":\"transport\",\"kind\":\"usb\"}");assert(atomic_load(&s_epoch)==2U);
    event(0,VK_INPUT_TRANSITION_CLICK);assert(((fake_queue_t*)s_tx)->count==0U);
    cmd("{\"event\":\"nk_policy\",\"epoch\":1,\"request_id\":3,\"voice_key\":\"none\"}");receipt("wrong_epoch");
    puts("key-only NONE/four-key/release/epoch/idempotence tests passed");recovery_tests();return 0;
}
