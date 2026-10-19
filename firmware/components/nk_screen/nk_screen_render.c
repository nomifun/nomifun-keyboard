#include "nk_screen.h"
#include <string.h>
static const char *const names[]={"connecting","sleeping","ready","starting","listening","recognizing","polishing","error"};
static const char *const labels[]={"LINKING","SLEEPY","READY","MIC START","LISTENING","ONE MOMENT","POLISHING","OOPS!"};
static const char *const hints[]={"USB / NOMIFUN","K1 TO WAKE ME","HOLD K4 TO TALK","SYSTEM MICROPHONE","I AM ALL EARS","FINALIZING SPEECH","KEEPING YOUR MEANING","READY WHEN YOU ARE"};
static const uint16_t colors[]={0x7c9f,0x6b6f,0x4ff9,0xff4c,0x4ff9,0x651f,0xbcdf,0xfb70};
_Static_assert(sizeof(names)/sizeof(names[0])==NK_STATE_COUNT,"screen state names");
_Static_assert(sizeof(labels)/sizeof(labels[0])==NK_STATE_COUNT,"screen state labels");
_Static_assert(sizeof(hints)/sizeof(hints[0])==NK_STATE_COUNT,"screen state hints");
_Static_assert(sizeof(colors)/sizeof(colors[0])==NK_STATE_COUNT,"screen state colors");
static const uint8_t glyphs[38][7]={
 {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},{30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},{14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},{7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},{17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},{30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},{15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},{17,17,17,17,17,10,4},{17,17,17,21,21,27,17},{17,17,10,4,10,17,17},{17,17,10,4,4,4,4},{31,1,2,4,8,16,31},
 {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},{30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},{14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},{14,17,17,15,1,1,14},{4,4,4,4,4,0,4},{0,1,2,4,8,16,0}};
bool nk_screen_parse(const char *name,nk_screen_state_t *state){if(!name||!state)return false;for(unsigned i=0;i<NK_STATE_COUNT;i++)if(strcmp(name,names[i])==0){*state=(nk_screen_state_t)i;return true;}return false;}
const char *nk_screen_name(nk_screen_state_t s){return s<NK_STATE_COUNT?names[s]:"error";}
typedef struct { uint16_t *pixels; int origin,rows; } canvas_t;
static void rect(canvas_t *p,int x,int y,int w,int h,uint16_t c){for(int yy=y;yy<y+h;yy++)for(int xx=x;xx<x+w;xx++)if(xx>=0&&xx<NK_SCREEN_WIDTH&&yy>=p->origin&&yy<p->origin+p->rows)p->pixels[(yy-p->origin)*NK_SCREEN_WIDTH+xx]=c;}
static void roundrect(canvas_t*p,int x,int y,int w,int h,int r,uint16_t c){for(int yy=0;yy<h;yy++)for(int xx=0;xx<w;xx++){int dx=xx<r?r-xx:xx>=w-r?xx-(w-r-1):0;int dy=yy<r?r-yy:yy>=h-r?yy-(h-r-1):0;if(dx*dx+dy*dy<=r*r)rect(p,x+xx,y+yy,1,1,c);}}
static void text(canvas_t*p,const char*s,int x,int y,int scale,uint16_t c){for(;*s;s++,x+=6*scale){int i=*s>='A'&&*s<='Z'?*s-'A':*s>='0'&&*s<='9'?26+*s-'0':*s=='!'?36:*s=='/'?37:-1;if(i<0)continue;for(int yy=0;yy<7;yy++)for(int xx=0;xx<5;xx++)if(glyphs[i][yy]&(1U<<(4-xx)))rect(p,x+xx*scale,y+yy*scale,scale,scale,c);}}
static void render(canvas_t*p,nk_screen_state_t state,uint32_t now,int key,uint32_t age){
 if(!p)return;
 if(state>=NK_STATE_COUNT)state=NK_ERROR;
 for(unsigned i=0;i<(unsigned)(NK_SCREEN_WIDTH*p->rows);i++)p->pixels[i]=0x0843;
 uint16_t accent=colors[state];int pulse=(int)((now/80U)%20U);if(pulse>10)pulse=20-pulse;int breathe=pulse/4;
 text(p,"NOMI",17,10,1,0x8c71);text(p,"SYSTEM MIC",300,10,1,0x8c71);
 int blink=(now%5200U)>5000U;int eye_y=39+breathe;
 if(state==NK_SLEEPING){roundrect(p,29,61,27,5,2,accent);roundrect(p,73,61,27,5,2,accent);text(p,"Z",99,35-(int)(now/400U%3U)*3,1,accent);}
 else{int h=blink?6:40;int y=blink?eye_y+17:eye_y;roundrect(p,29,y,27,h,9,accent);roundrect(p,73,y,27,h,9,accent);if(!blink){int shift=age<500U&&key>=0?(key-1)*2:0;roundrect(p,38+shift,y+10,9,17,4,0x0843);roundrect(p,82+shift,y+10,9,17,4,0x0843);rect(p,39+shift,y+11,3,3,0xffff);rect(p,83+shift,y+11,3,3,0xffff);}}
 text(p,labels[state],132,42,2,accent);text(p,hints[state],133,66,1,0xbdf7);
 if(state==NK_LISTENING||state==NK_STARTING||state==NK_RECOGNIZING||state==NK_POLISHING){for(int i=0;i<23;i++){int bar=3+(int)((now/75U+(unsigned)i*7U)%13U);roundrect(p,133+i*10,83-bar/2,4,bar,2,accent);}}
 else{rect(p,133,84,225,2,0x2107);rect(p,133,84,30+pulse*14,2,accent);}
 const char *const keys[]={"K1 MAIN","K2 POLISH","K3 CANCEL","K4 TALK"};
 for(int i=0;i<4;i++){int x=14+i*102;bool active=key==i&&age<450U;roundrect(p,x,109,94,24,6,active?accent:0x18c7);text(p,keys[i],x+7,117,1,active?0x0843:0x9d36);}
}

void nk_screen_render(uint16_t *pixels,nk_screen_state_t state,uint32_t now,int key,uint32_t age){if(!pixels)return;canvas_t canvas={pixels,0,NK_SCREEN_HEIGHT};render(&canvas,state,now,key,age);}
void nk_screen_render_strip(uint16_t *pixels,nk_screen_state_t state,uint32_t now,int key,uint32_t age,int origin,int rows){if(!pixels||origin<0||rows<=0||origin+rows>NK_SCREEN_HEIGHT)return;canvas_t canvas={pixels,origin,rows};render(&canvas,state,now,key,age);}
