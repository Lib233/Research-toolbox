""" combined orbital + searchable floating navigation.

This visualizes module selection only. The perspective is illustrative UI, not
scientific 3D reconstruction. Timed animation is scoped to the popup and can
be paused; closing the popup cancels scheduled callbacks.
"""
from __future__ import annotations
import math
import tkinter as tk
from tkinter import ttk
from ui_spatial89 import MODULES
from ui_copy104 import display_name

class SpatialModuleLauncher(tk.Toplevel):
    """Large, centered, animated orbital navigator with always-available search."""
    def __init__(self, master, on_select, font=None, theme='经典蓝色'):
        super().__init__(master)
        self.title('模块导航 · 空间工作台')
        self.minsize(790, 550)
        self.on_select=on_select
        self.theme=theme
        self.angle=0.0
        self.active=getattr(master, 'module', None) or MODULES[0]
        self.animate=tk.BooleanVar(value=True)
        self._timer=None
        self._drag=None
        self._moved=False
        self.hits=[]
        self.keyword=tk.StringVar(value='')
        self.selection=tk.StringVar(value=self.active)
        self._set_colors()
        self.configure(bg=self.bg)
        self._build(font)
        self._center(master)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Escape>', lambda e:self.close())
        self.bind('<Left>',lambda e:self.rotate(-.17))
        self.bind('<Right>',lambda e:self.rotate(.17))
        self.after(90,self._tick)
        self.after_idle(self.draw)

    def _set_colors(self):
        palettes={
            '经典蓝色':('#101D33','#172C43','#7CCBD8','#F3F9FF','#AFCCDA','#203D57'),
            '深色配色':('#111726','#1D2940','#B6A3F4','#F6F3FF','#BDCAE5','#344360'),
            '粉色配色':('#FFF1F7','#FFE5F0','#D879AA','#683E61','#976D88','#FFCADF'),
        }
        self.bg,self.panel,self.accent,self.text,self.muted,self.ring=palettes.get(self.theme,palettes['经典蓝色'])
        self.button_text='#FFFFFF' if self.theme!='粉色配色' else '#5C2E4B'

    def _center(self,master):
        self.update_idletasks()
        sw=max(master.winfo_screenwidth(),900);sh=max(master.winfo_screenheight(),650)
        w=min(1160,sw-90);h=min(790,sh-90)
        x=max(0,(sw-w)//2);y=max(0,(sh-h)//2)
        self.geometry(f'{w}x{h}+{x}+{y}')

    def _build(self,font):
        top=tk.Frame(self,bg=self.bg);top.pack(fill='x',padx=25,pady=(20,12))
        tk.Label(top,text='选择科研任务',font=font,bg=self.bg,fg=self.text).pack(side='left')
        tk.Button(top,text='关闭  ×',command=self.close,bg=self.panel,fg=self.text,relief='flat',padx=16,pady=8).pack(side='right')
        body=tk.Frame(self,bg=self.bg);body.pack(fill='both',expand=True,padx=23,pady=(0,20))
        left=tk.Frame(body,bg=self.bg);left.pack(side='left',fill='both',expand=True)
        self.canvas=tk.Canvas(left,bg=self.bg,highlightthickness=0,cursor='hand2',takefocus=True)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<ButtonPress-1>',self._press)
        self.canvas.bind('<B1-Motion>',self._motion)
        self.canvas.bind('<ButtonRelease-1>',self._release)
        self.canvas.bind('<MouseWheel>',lambda e:self.rotate(-.18 if e.delta>0 else .18))
        controls=tk.Frame(left,bg=self.bg);controls.pack(fill='x',padx=12,pady=(0,8))
        tk.Button(controls,text='◀',command=lambda:self.rotate(-.18),bg=self.panel,fg=self.text,relief='flat',padx=14,pady=8).pack(side='left')
        tk.Checkbutton(controls,text='缓慢旋转',variable=self.animate, bg=self.bg,fg=self.text,
            selectcolor=self.panel,activebackground=self.bg,activeforeground=self.text).pack(side='left',padx=15)
        tk.Button(controls,text='▶',command=lambda:self.rotate(.18),bg=self.panel,fg=self.text,relief='flat',padx=14,pady=8).pack(side='left')
        right=tk.Frame(body,bg=self.panel,width=300);right.pack(side='right',fill='y',padx=(14,0))
        right.pack_propagate(False)
        tk.Label(right,text='模块查找',font=font,bg=self.panel,fg=self.text).pack(anchor='w',padx=18,pady=(20,6))
        self.search=tk.Entry(right,textvariable=self.keyword,font=font,relief='flat',bg='#FFFFFF' if self.theme=='粉色配色' else '#F7FAFF',fg='#273A52')
        self.search.pack(fill='x',padx=18,ipady=8)
        self.keyword.trace_add('write',lambda *_:self._populate())
        tk.Label(right,text='可搜索模块；点击列表或圆环节点打开。',bg=self.panel,fg=self.muted,wraplength=255,justify='left').pack(anchor='w',padx=18,pady=(9,12))
        listbox=tk.Frame(right,bg=self.panel);listbox.pack(fill='both',expand=True,padx=12)
        self.list_canvas=tk.Canvas(listbox,bg=self.panel,highlightthickness=0)
        scrollbar=ttk.Scrollbar(listbox,orient='vertical',command=self.list_canvas.yview)
        scrollbar.pack(side='right',fill='y');self.list_canvas.pack(side='left',fill='both',expand=True)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        self.items=tk.Frame(self.list_canvas,bg=self.panel)
        win=self.list_canvas.create_window((0,0),window=self.items,anchor='nw')
        self.items.bind('<Configure>',lambda e:self.list_canvas.configure(scrollregion=self.list_canvas.bbox('all')))
        self.list_canvas.bind('<Configure>',lambda e:self.list_canvas.itemconfigure(win,width=e.width))
        self._populate()
        self.selection_label=tk.Label(right,text='当前：'+display_name(self.active),font=font,bg=self.panel,fg=self.text,wraplength=270)
        self.selection_label.pack(padx=12,pady=(9,6))
        tk.Button(right,text='打开所选模块',command=lambda:self.select(self.active),bg=self.accent,
            fg=self.button_text,relief='flat',padx=12,pady=12).pack(fill='x',padx=16,pady=(2,20))

    def _populate(self):
        for child in self.items.winfo_children():child.destroy()
        query=self.keyword.get().strip().casefold()
        matches=[(i,name) for i,name in enumerate(MODULES,1) if query in name.casefold() or query in display_name(name).casefold() or query in f'{i:02d}']
        if not matches:tk.Label(self.items,text='没有匹配的模块',bg=self.panel,fg=self.muted).pack(pady=16)
        for i,name in matches:
            bg='#FFEAF3' if self.theme=='粉色配色' else '#2A3E59'
            fg='#593B58' if self.theme=='粉色配色' else '#ECF5FF'
            tk.Button(self.items,text=f'{i:02d}   {display_name(name)}  ›',anchor='w',bg=bg,fg=fg,relief='flat',
                padx=11,pady=9,command=lambda n=name:self.select(n)).pack(fill='x',padx=6,pady=3)

    def rotate(self,delta):
        self.angle+=delta
        self.draw()
        return 'break'

    def _press(self,e):self._drag=(e.x,e.y);self._moved=False
    def _motion(self,e):
        if self._drag is None:return
        dx=e.x-self._drag[0]
        if abs(dx)>2:
            self._moved=True;self.angle+=dx*.009;self._drag=(e.x,e.y);self.draw()
    def _release(self,e):
        if self._drag is None:return
        self._drag=None
        if self._moved:return
        for x,y,r,name in reversed(self.hits):
            if (e.x-x)**2+(e.y-y)**2<=(r+9)**2:
                self.select(name);break

    def select(self,name):
        if name not in MODULES:return
        self.active=name;self.selection.set(name)
        self.on_select(name)
        self.close()

    def _tick(self):
        self._timer=None
        if not self.winfo_exists():return
        if self.animate.get() and self._drag is None:
            self.angle+=.012
            self.draw()
        self._timer=self.after(65,self._tick)

    def draw(self):
        if not getattr(self,'canvas',None):return
        c=self.canvas
        try:w=c.winfo_width();h=c.winfo_height()
        except tk.TclError:return
        if w<30 or h<30:return
        c.delete('all');cx=w*.5;cy=h*.49
        r=min(w*.38,h*.38,260)
        for k in (1,.76,.45):
            c.create_oval(cx-r*k,cy-r*k*.70,cx+r*k,cy+r*k*.70,outline=self.ring,width=1)
        c.create_oval(cx-65,cy-65,cx+65,cy+65,fill=self.panel,outline=self.accent,width=2)
        c.create_text(cx,cy-11,text='RESEARCH',fill=self.text,font=('Arial',12,'bold'))
        c.create_text(cx,cy+12,text='TOOLBOX',fill=self.muted,font=('Arial',11))
        nodes=[];n=len(MODULES)
        for i,name in enumerate(MODULES):
            theta=i*2*math.pi/n+self.angle
            depth=math.cos(theta)
            perspective=1/(1.20-.20*depth)
            x=cx+r*math.sin(theta)*perspective
            y=cy+(r*.47*math.cos(theta)+r*.08*math.sin(2*theta))*perspective
            radius=(13+5*(depth+1)/2)*perspective
            nodes.append((depth,x,y,radius,name,i+1))
        self.hits=[]
        for z,x,y,rad,name,i in sorted(nodes):
            is_active=name==self.active
            shade=self.ring if z<-.18 else self.accent
            rnode=rad+(4 if is_active else 0)
            c.create_oval(x-rnode+4,y-rnode+5,x+rnode+4,y+rnode+5,fill=self.panel,outline='')
            c.create_oval(x-rnode,y-rnode,x+rnode,y+rnode,fill=shade,outline=self.text if is_active else self.ring,width=2 if is_active else 1)
            c.create_oval(x-rnode*.55,y-rnode*.66,x,y-rnode*.13,fill=self.text,stipple='gray50',outline='')
            c.create_text(x,y,text=str(i),fill=self.bg,font=('Arial',10,'bold'))
            self.hits.append((x,y,rnode,name))
        c.create_text(cx,cy+r*.75+18,text=display_name(self.active),fill=self.text,font=('Arial',13,'bold'))
        c.create_text(cx,cy+r*.75+42,text='拖拽或滚轮旋转 · 点击节点进入',fill=self.muted,font=('Arial',10))

    def close(self):
        if self._timer is not None:
            try:self.after_cancel(self._timer)
            except tk.TclError:pass
        self._timer=None
        try:self.master._spatial_window=None
        except Exception:pass
        self.destroy()
