"""Research Toolbox : accessible projected-3D orbital module launcher.

Only Tkinter Canvas projection is used; this is a navigation visualization,
not 3D experimental reconstruction. No change to numerical data or units.
"""
from __future__ import annotations
import math
import tkinter as tk
from tkinter import ttk
from ui_copy104 import display_name

MODULES=('项目工作流','数据质检','批量力学','力学分析','高级统计',
         '轨迹人工修正','视频追踪','运动关系分析','显微图像','信号处理',
         '多源同步','独立样本统计','曲线拟合','公式优化','实验数据优化',
         '分析结果整理','论文绘图')

class OrbitalNavigation(tk.Frame):
    """Interactive circular projection: clickable front nodes + always usable combobox.

    Drag or wheel to rotate. Keyboard Left/Right rotates; Enter opens selected.
    Canvas nodes use simulated depth and highlights, not an external rendering engine.
    """
    def __init__(self,master,on_select,font=None,width=294):
        super().__init__(master,bg='#14283F',width=width)
        self.pack_propagate(False)
        self.on_select=on_select
        self.angle=0.0
        self.active=MODULES[0]
        self.drag_x=None
        self.drag_origin=None
        self.hits=[]
        self.accent='#79CED6'
        self.bg='#14283F'
        self.fg='#EBF5FF'
        self.font=font
        tk.Label(self,text='模块环形导航',font=font,fg=self.fg,bg=self.bg).pack(padx=12,pady=(15,2),anchor='w')
        tk.Label(self,text='拖动圆环或滚轮旋转 · 点击节点进入模块',font=font,fg='#BCD3E2',bg=self.bg,
                 wraplength=width-28,justify='left').pack(padx=12,pady=(0,8),anchor='w')
        self.canvas=tk.Canvas(self,bg=self.bg,highlightthickness=0,height=330,cursor='hand2')
        self.canvas.pack(fill='x',expand=False,padx=3)
        self.canvas.bind('<Configure>',lambda e:self.redraw())
        self.canvas.bind('<ButtonPress-1>',self._press)
        self.canvas.bind('<ButtonRelease-1>',self._release)
        self.canvas.bind('<B1-Motion>',self._drag)
        self.canvas.bind('<MouseWheel>',self._wheel)
        self.canvas.bind('<Button-4>',lambda e:self.rotate(-1))
        self.canvas.bind('<Button-5>',lambda e:self.rotate(1))
        self.canvas.bind('<Left>',lambda e:self.rotate(-1))
        self.canvas.bind('<Right>',lambda e:self.rotate(1))
        self.canvas.bind('<Return>',lambda e:self.on_select(next((m for m in MODULES if display_name(m)==self.pick.get()),self.pick.get())))
        self.canvas.configure(takefocus=1)
        controls=tk.Frame(self,bg=self.bg);controls.pack(fill='x',padx=10,pady=(4,7))
        tk.Button(controls,text='◀',width=4,command=lambda:self.rotate(-1),bg='#294F67',fg='white',relief='flat').pack(side='left')
        tk.Button(controls,text='▶',width=4,command=lambda:self.rotate(1),bg='#294F67',fg='white',relief='flat').pack(side='right')
        tk.Label(controls,text='转动圆环',bg=self.bg,fg=self.fg,font=font).pack(expand=True)
        self.pick=tk.StringVar(value=display_name(self.active))
        self.selector=ttk.Combobox(self,values=[display_name(m) for m in MODULES],textvariable=self.pick,state='readonly')
        self.selector.pack(fill='x',padx=12,pady=(5,4))
        self.selector.bind('<<ComboboxSelected>>',lambda e:self.select_from_list())
        tk.Button(self,text='打开选中模块',command=lambda:self.on_select(next((m for m in MODULES if display_name(m)==self.pick.get()),self.pick.get())),
                  bg='#D4F2F4',fg='#163D51',relief='flat',padx=10,pady=9,cursor='hand2').pack(fill='x',padx=12,pady=(5,14))
        self.after_idle(self.redraw)

    def recolor(self,bg='#14283F',accent='#79CED6'):
        self.bg=bg;self.accent=accent
        self.configure(bg=bg)
        for child in self.winfo_children():
            if isinstance(child,(tk.Label,tk.Frame,tk.Canvas)):
                try:child.configure(bg=bg)
                except tk.TclError:pass
        self.redraw()

    def select_from_list(self):
        name=next((m for m in MODULES if display_name(m)==self.pick.get()),self.pick.get())
        self.active=name
        i=MODULES.index(name)
        self.angle=-(2*math.pi*i/len(MODULES))
        self.redraw()
        self.on_select(name)

    def set_active(self,name):
        if name in MODULES:
            self.active=name;self.pick.set(display_name(name));self.redraw()

    def rotate(self,steps):
        self.angle+=steps*(2*math.pi/len(MODULES))
        self.redraw()

    def _wheel(self,e):
        self.rotate(-1 if e.delta>0 else 1)
        return 'break'

    def _press(self,e):
        self.drag_x=e.x
        self.drag_origin=e.x
        self.canvas.focus_set()

    def _drag(self,e):
        if self.drag_x is None:return
        dx=e.x-self.drag_x
        if abs(dx)>3:
            self.angle+=dx*.014;self.drag_x=e.x
            self.redraw()

    def _release(self,e):
        if self.drag_x is None:return
                                                                      
        if abs(e.x-self.drag_origin)<7:
            for x,y,r,name in reversed(self.hits):
                if (e.x-x)**2+(e.y-y)**2<=(r+8)**2:
                    self.set_active(name);self.on_select(name);break
        self.drag_x=None;self.drag_origin=None

    def redraw(self):
        c=self.canvas
        try:w=max(c.winfo_width(),230);h=330
        except tk.TclError:return
        c.delete('all');cx=w/2;cy=162;R=min(112,w*.38)
        c.create_oval(cx-R*.95,cy-R*.95,cx+R*.95,cy+R*.95,outline='#2D617B',width=2)
        c.create_oval(cx-R,cy-R*.41,cx+R,cy+R*.41,outline='#426B85',width=1)
        c.create_oval(cx-R*.55,cy-R,cx+R*.55,cy+R,outline='#2F5671',width=1)
        c.create_oval(cx-36,cy-36,cx+36,cy+36,fill='#20435C',outline='#63B9C6',width=2)
        c.create_text(cx,cy-5,text='RT',fill=self.fg,font=('Arial',16,'bold'))
        c.create_text(cx,cy+15,text='Modules',fill='#9CC7D8',font=('Arial',8))
        nodes=[]
        self.hits=[]
        n=len(MODULES)
                                                                               
                                                                             
        for i,name in enumerate(MODULES):
            theta=2*math.pi*i/n+self.angle
            z=math.cos(theta)
            pers=1/(1.24-.23*z)
            x=cx+R*math.sin(theta)*pers
            y=cy+(R*.60*math.cos(theta)+18*math.sin(theta*2+.3))*pers
            rad=(9.5+6.2*(z+1)/2)*pers
            nodes.append((z,x,y,rad,name))
        for z,x,y,r,name in sorted(nodes):
            col='#306079' if z<-.12 else ('#B8EDF2' if name==self.active else '#6FC6D0')
            if name==self.active:r+=3
            c.create_oval(x-r+3,y-r+4,x+r+3,y+r+4,fill='#102D43',outline='')
            c.create_oval(x-r,y-r,x+r,y+r,fill=col,outline='#D0F7FC' if name==self.active else '#487A8A',width=2 if name==self.active else 1)
            c.create_oval(x-r*.56,y-r*.67,x+r*.1,y-r*.05,fill='#E5FFFF' if z>.0 else '#648B9D',outline='')
            if z>=-.16:
                i=MODULES.index(name)+1
                c.create_text(x,y,text=str(i),fill='#15394D' if z>=0 else '#E4F3FC',font=('Arial',8,'bold'))
            self.hits.append((x,y,r,name))
        c.create_text(cx,287,text=f'当前模块：{display_name(self.active)}',fill='#E6F7FA',font=('Microsoft YaHei',10,'bold'))
        c.create_text(cx,315,text='滚轮旋转 · 点击节点 · 或下方直接选择',fill='#B7D3E3',font=('Microsoft YaHei',8))

class ModulePalette(tk.Toplevel):
    """Searchable popup launcher; keyboard-first and scrollbar based."""
    def __init__(self,master,on_select,font=None):
        super().__init__(master)
        self.title('模块选择 · 浮动工作台');self.geometry('690x565');self.minsize(465,350)
        self.transient(master)
        self.configure(bg='#F4F8FB')
        self.on_select=on_select
        h=tk.Frame(self,bg='#E9F2F8');h.pack(fill='x')
        tk.Label(h,text='选择一个科研任务',bg='#E9F2F8',fg='#203D55',font=font).pack(anchor='w',padx=18,pady=(18,8))
        self.keyword=tk.StringVar(value='')
        ent=tk.Entry(h,textvariable=self.keyword,relief='flat',font=font)
        ent.pack(fill='x',padx=18,pady=(0,15),ipady=6)
        ent.focus_set();ent.bind('<Escape>',lambda e:self.destroy())
        self.keyword.trace_add('write',lambda *_:self._populate())
        self.cv=tk.Canvas(self,bg='#F4F8FB',highlightthickness=0)
        vs=ttk.Scrollbar(self,orient='vertical',command=self.cv.yview)
        self.cv.configure(yscrollcommand=vs.set)
        self.cv.pack(side='left',fill='both',expand=True);vs.pack(side='right',fill='y')
        self.content=tk.Frame(self.cv,bg='#F4F8FB')
        win=self.cv.create_window((0,0),window=self.content,anchor='nw')
        self.content.bind('<Configure>',lambda e:self.cv.configure(scrollregion=self.cv.bbox('all')))
        self.cv.bind('<Configure>',lambda e:self.cv.itemconfigure(win,width=e.width))
        self._populate()
        self.after_idle(self.lift)

    def _populate(self):
        for w in self.content.winfo_children():w.destroy()
        terms=self.keyword.get().strip().lower()
        matches=[m for m in MODULES if terms in m.lower() or terms in display_name(m).lower()]
        if not matches:
            tk.Label(self.content,text='没有匹配的模块',bg='#F4F8FB',fg='#506679').pack(pady=20)
        for i,name in enumerate(matches):
            row=tk.Frame(self.content,bg='white',highlightthickness=1,highlightbackground='#DDE6ED');row.pack(fill='x',padx=16,pady=4)
            original=MODULES.index(name)+1
            tk.Button(row,text=f'{original:02d}   {display_name(name)}    ›',bg='white',fg='#264C63',relief='flat',anchor='w',cursor='hand2',
                      padx=18,pady=12,command=lambda m=name:(self.on_select(m),self.destroy())).pack(fill='x')
