"""Interactive scientific annotation: native video coordinates, independent of display zoom.

The magnifier exposes individual ORIGINAL pixels and permits fractional-coordinate
entry, but fractional numbers do not imply experimentally validated accuracy.
"""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from PIL import Image,ImageTk

class VideoPointEditor(tk.Toplevel):
    def __init__(self,master, video_path, output_callback=None, track_file=None, initial_csv=None, calibration_callback=None):
        super().__init__(master)
        self.title('精细视频标注器 · 多特征点 / 逐帧 / 原始像素坐标')
        sw,sh=self.winfo_screenwidth(),self.winfo_screenheight()
        self.mag_size=220 if sh<=790 else (280 if sh<=950 else 320)
        self.geometry(f'{min(1230,max(880,sw-55))}x{min(830,max(570,sh-75))}')
        self.minsize(870,570)
        self.video=Path(video_path)
        self.cap=cv2.VideoCapture(str(self.video))
        if not self.cap.isOpened():
            self.destroy();raise ValueError('无法打开视频：'+str(video_path))
        self.length=int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps=float(self.cap.get(cv2.CAP_PROP_FPS))
        if not np.isfinite(self.fps) or self.fps<=0:
            self.cap.release();self.destroy();raise ValueError('视频没有有效帧率，暂时无法逐帧标注带时间的数据。')
        ok,self.frame=self.cap.read()
        if not ok:
            self.cap.release();self.destroy();raise ValueError('视频没有可解码的首帧。')
        self.h,self.w=self.frame.shape[:2]
        self.current=0;self.photo=None;self.mphoto=None;self._slide_task=None
        self.anchors={};self.output_callback=output_callback;self.calibration_callback=calibration_callback
        self.calibrating=False;self.scale_points=[]
        self.auto={}
        if track_file and Path(track_file).is_file():
            try:
                d=pd.read_csv(track_file)
                if {'frame','point_id','x_px','y_px'}.issubset(d):
                    for r in d[['frame','point_id','x_px','y_px']].itertuples(index=False):
                        if pd.notna(r.x_px) and pd.notna(r.y_px):
                            self.auto[(int(r.frame),str(r.point_id))]=(float(r.x_px),float(r.y_px))
                elif {'frame','x_px','y_px'}.issubset(d):
                    for r in d[['frame','x_px','y_px']].itertuples(index=False):
                        if pd.notna(r.x_px) and pd.notna(r.y_px):self.auto[(int(r.frame),'center')]=(float(r.x_px),float(r.y_px))
            except Exception:pass
        default_point='P1'
        if self.auto and {name for _,name in self.auto}=={'center'}:default_point='center'
        self.pt=tk.StringVar(value=default_point);self.xval=tk.StringVar();self.yval=tk.StringVar()
        self.frame_var=tk.IntVar(value=0)
        self.zoom=tk.DoubleVar(value=1.0)
        self.mag_radius=tk.IntVar(value=12)
        self.message=tk.StringVar(value='先给特征点命名，然后在左侧画面或右侧精细放大镜中单击标点。')
        self.cursor_xy=(self.w/2,self.h/2)
        self._layout()
        if initial_csv and Path(initial_csv).is_file():self.import_csv(initial_csv)
        self.show_frame(0)
        self.protocol('WM_DELETE_WINDOW',self.close)

    def _layout(self):
        top=tk.Frame(self,bg='#E8F2F7');top.pack(fill='x')
        tk.Label(top,text='逐帧点选真实物理特征 · 可添加多个点',bg='#E8F2F7',fg='#163047',font=('Microsoft YaHei UI',13,'bold')).pack(side='left',padx=15,pady=9)
        tk.Label(top,text=f'原视频：{self.w}×{self.h} px   ·   {self.fps:.4g} FPS   ·   {self.length or "未知"} 帧',bg='#E8F2F7',fg='#41617C').pack(side='right',padx=15)
        tools=tk.Frame(self);tools.pack(fill='x',padx=12,pady=9)
        tk.Label(tools,text='当前点名').pack(side='left')
        self.point_combo=ttk.Combobox(tools,textvariable=self.pt,width=15,values=['P1','P2','body','head','tail','foot_L','foot_R','wing_hinge','wing_tip'])
        self.point_combo.pack(side='left',padx=7)
        self.point_combo.bind('<<ComboboxSelected>>',lambda e:self._update_entries())
        self.point_combo.bind('<Return>',lambda e:self._update_entries())
        tk.Label(tools,text='X / Y（原视频像素，左上角为 0,0）').pack(side='left',padx=(14,5))
        tk.Entry(tools,textvariable=self.xval,width=11).pack(side='left',padx=2)
        tk.Entry(tools,textvariable=self.yval,width=11).pack(side='left',padx=2)
        tk.Button(tools,text='确认输入坐标',command=self.commit_xy,bg='#CBE8EF').pack(side='left',padx=6)
        tk.Button(tools,text='载入本帧自动坐标',command=self.load_auto).pack(side='left',padx=3)
        tk.Button(tools,text='设为重追踪锚点',command=self.mark_retrack_anchor,bg='#D4F0E7',padx=6).pack(side='left',padx=3)
        tk.Button(tools,text='删除本帧标点',command=self.delete_current).pack(side='left',padx=3)
        view=tk.Frame(self);view.pack(fill='both',expand=True,padx=12)
        left=tk.Frame(view);left.pack(side='left',fill='both',expand=True)
        self.canvas=tk.Canvas(left,bg='#101820',highlightthickness=0,cursor='crosshair')
        sx=ttk.Scrollbar(left,orient='horizontal',command=self.canvas.xview)
        sy=ttk.Scrollbar(left,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
        self.canvas.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        left.grid_rowconfigure(0,weight=1);left.grid_columnconfigure(0,weight=1)
        self.canvas.bind('<Button-1>',self.canvas_click)
        self.canvas.bind('<Motion>',self.main_motion)
        self.canvas.bind('<Configure>',lambda e:self._render())
        right=tk.Frame(view,width=350,bg='#F3F7FA');right.pack(side='right',fill='y',padx=(10,0));right.pack_propagate(False)
        tk.Label(right,text='精细放大镜 · 点中图像即可标记',font=('Microsoft YaHei UI',11,'bold'),bg='#F3F7FA',fg='#17405D').pack(pady=(12,5))
        tk.Label(right,text='放大后每个原始像素可占多个屏幕像素。\n支持坐标小数输入和 0.1 px 微调；\n不代表标注的真实精度达到 0.1 px。',bg='#F3F7FA',justify='left',fg='#536777').pack(pady=(0,9))
        self.mag=tk.Canvas(right,width=self.mag_size,height=self.mag_size,bg='#20242B',cursor='crosshair')
        self.mag.pack(pady=5)
        self.mag.bind('<Button-1>',self.mag_click)
        mags=tk.Frame(right,bg='#F3F7FA');mags.pack(pady=5)
        tk.Label(mags,text='放大范围半径 (px)',bg='#F3F7FA').pack(side='left')
        ttk.Combobox(mags,textvariable=self.mag_radius,values=[5,8,12,20,32],width=5,state='readonly').pack(side='left',padx=8)
        tk.Button(mags,text='更新',command=self._render_magnifier).pack(side='left')
        fine=tk.Frame(right,bg='#F3F7FA');fine.pack(pady=9)
        for label,dx,dy in [('←',-.1,0),('→',.1,0),('↑',0,-.1),('↓',0,.1)]:
            tk.Button(fine,text=label,command=lambda dx=dx,dy=dy:self.nudge(dx,dy),width=4).pack(side='left',padx=3)
        tk.Label(right,text='上方微调针对已标注的当前帧特征点。',bg='#F3F7FA',fg='#536777').pack()
        self.anchor_list=tk.Listbox(right,height=3,exportselection=False)
        self.anchor_list.pack(fill='both',expand=True,padx=11,pady=(13,10))
        self.anchor_list.bind('<<ListboxSelect>>',self.jump_selected)
        bottom=tk.Frame(self);bottom.pack(fill='x',padx=12,pady=(8,3))
        tk.Button(bottom,text='◀ 上一帧',command=lambda:self.show_frame(self.current-1)).pack(side='left',padx=3)
        tk.Button(bottom,text='下一帧 ▶',command=lambda:self.show_frame(self.current+1)).pack(side='left',padx=3)
        tk.Label(bottom,text='跳转帧号').pack(side='left',padx=(12,4))
        self.jump_var=tk.StringVar(value='0')
        tk.Entry(bottom,textvariable=self.jump_var,width=9).pack(side='left')
        tk.Button(bottom,text='跳转',command=self.jump_to).pack(side='left',padx=4)
        tk.Label(bottom,text='主画面放大').pack(side='left',padx=(15,3))
        self.zoom_choice=ttk.Combobox(bottom,values=['适合窗口','100%','200%','400%','800%'],width=11,state='readonly')
        self.zoom_choice.set('适合窗口');self.zoom_choice.pack(side='left',padx=4)
        self.zoom_choice.bind('<<ComboboxSelected>>',lambda e:self._render())
        tk.Button(bottom,text='查看所有标点',command=self.show_marks).pack(side='right',padx=4)
        tk.Button(bottom,text='在画面上两点标定比例尺',command=self.start_calibration).pack(side='right',padx=4)
        tk.Button(bottom,text='读取已有标注 CSV',command=self.load_csv).pack(side='right',padx=4)
        tk.Button(bottom,text='保存标注并返回模块',command=self.save,bg='#0E7490',fg='white',padx=11).pack(side='right',padx=5)
        timeline=tk.Frame(self);timeline.pack(fill='x',padx=16)
        self.slider=tk.Scale(timeline,from_=0,to=max(0,self.length-1),variable=self.frame_var,orient='horizontal',showvalue=0,
                             command=self.slide_frame,highlightthickness=0)
        self.slider.pack(fill='x')
        tk.Label(self,textvariable=self.message,anchor='w',fg='#1B5E72',wraplength=1120).pack(fill='x',padx=17,pady=(4,10))

    def show_frame(self,index):
        index=max(0,int(index))
        if self.length>0:index=min(index,self.length-1)
        if index!=self.current:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES,index)
            ok,frame=self.cap.read()
            if not ok:self.message.set(f'第 {index} 帧解码失败；请检查视频。');return
            self.frame=frame
        self.current=index
        self.frame_var.set(index);self.jump_var.set(str(index))
        self._render();self._update_entries()
        self.message.set(f'第 {index} 帧 · {index/self.fps:.5f} 秒（基于报告FPS） · {len(self.anchors)} 条人工标注。点击图像，坐标自动换算为原始像素。')

    def slide_frame(self,_):
                                                                               
                                                                         
        index=int(self.frame_var.get())
        if index==self.current:return
        if self._slide_task is not None:self.after_cancel(self._slide_task)
        self._slide_task=self.after(90,lambda idx=index:self._seek_from_slider(idx))

    def _seek_from_slider(self,index):
        self._slide_task=None
        if self.winfo_exists():self.show_frame(index)

    def jump_to(self):
        try:self.show_frame(int(self.jump_var.get()))
        except ValueError:messagebox.showerror('帧号非法','请输入整数帧号。',parent=self)

    def _factor(self):
        text=self.zoom_choice.get()
        if text=='适合窗口':
            w=max(350,self.canvas.winfo_width()-20);h=max(280,self.canvas.winfo_height()-20)
            return min(w/self.w,h/self.h,3.)
        return {'100%':1.,'200%':2.,'400%':4.,'800%':8.}.get(text,1.)

    def _render(self):
        if not self.winfo_exists():return
        zoom=self._factor()
        aw=max(1,round(self.w*zoom));ah=max(1,round(self.h*zoom))
        if aw*ah>22_000_000:zoom*= (22_000_000/(aw*ah))**.5;aw=max(1,int(self.w*zoom));ah=max(1,int(self.h*zoom))
        self.view_factor=zoom
        rgb=cv2.cvtColor(self.frame,cv2.COLOR_BGR2RGB)
        pil=Image.fromarray(rgb).resize((aw,ah),Image.Resampling.BILINEAR)
        self.photo=ImageTk.PhotoImage(pil)
        self.canvas.delete('all');self.canvas.create_image(0,0,anchor='nw',image=self.photo)
        self.canvas.configure(scrollregion=(0,0,aw,ah))
        for (frame,point),(x,y) in self.auto.items():
            if frame==self.current:
                cx=x*zoom;cy=y*zoom
                self.canvas.create_oval(cx-5,cy-5,cx+5,cy+5,outline='#FFD166',width=2)
        for (frame,point),(x,y) in self.anchors.items():
            if frame!=self.current:continue
            cx=x*zoom;cy=y*zoom
            self.canvas.create_line(cx-10,cy,cx+10,cy,fill='#00F0FF',width=2)
            self.canvas.create_line(cx,cy-10,cx,cy+10,fill='#00F0FF',width=2)
            self.canvas.create_text(cx+9,cy-9,text=point,fill='#FDFDFD',anchor='sw')
        self._render_magnifier()
        self._refresh_list()

    def _refresh_list(self):
        if not hasattr(self,'anchor_list'):return
        self.anchor_list.delete(0,'end')
        for (frame,point),(x,y) in sorted(self.anchors.items()):
            self.anchor_list.insert('end',f'{frame:06d} · {point}: ({x:.3f}, {y:.3f})')

    def _update_entries(self):
        key=(self.current,self.pt.get().strip())
        xy=self.anchors.get(key,self.auto.get(key))
        self.xval.set(f'{xy[0]:.3f}' if xy else '')
        self.yval.set(f'{xy[1]:.3f}' if xy else '')
        if xy:self.cursor_xy=xy
        self._render_magnifier()

    def _store(self,x,y):
        name=self.pt.get().strip()
        if not name or '/' in name or '\\' in name or '\n' in name:
            messagebox.showerror('点名无效','请填写简短特征点名称，例如 foot_L、wing_tip。',parent=self);return
        if not (np.isfinite([x,y]).all() and 0<=x<self.w and 0<=y<self.h):
            messagebox.showerror('坐标超界',f'X 应在 [0,{self.w-1}]，Y 应在 [0,{self.h-1}]；坐标基于视频原始帧，不是显示窗口。',parent=self);return
        self.anchors[(self.current,name)]=(float(x),float(y))
        ids=sorted({pt for _,pt in self.anchors})
        self.point_combo.configure(values=ids+['P1','P2','body','head','tail','foot_L','foot_R','wing_hinge','wing_tip'])
        self.cursor_xy=(float(x),float(y))
        self.xval.set(f'{x:.4f}');self.yval.set(f'{y:.4f}')
        self._render();self.message.set(f'已记录第 {self.current} 帧：{name} = ({x:.4f}, {y:.4f}) px。保存后会进入算法；不要把鼠标标点精度当成实际运动精度。')

    def canvas_click(self,event):
        x=self.canvas.canvasx(event.x)/self.view_factor;y=self.canvas.canvasy(event.y)/self.view_factor
        self._capture_position(x,y)

    def main_motion(self,event):
        x=self.canvas.canvasx(event.x)/self.view_factor;y=self.canvas.canvasy(event.y)/self.view_factor
        if 0<=x<self.w and 0<=y<self.h:
            self.cursor_xy=(x,y);self._render_magnifier()

    def _render_magnifier(self):
        if not hasattr(self,'mag'):return
        x,y=self.cursor_xy
        r=int(self.mag_radius.get());r=max(4,min(40,r))
        size=2*r+1
        patch=np.zeros((size,size,3),dtype=np.uint8)+24
        xi=int(np.floor(x));yi=int(np.floor(y))
        x1=max(0,xi-r);y1=max(0,yi-r);x2=min(self.w,xi+r+1);y2=min(self.h,yi+r+1)
        if x2>x1 and y2>y1:
            crop=cv2.cvtColor(self.frame[y1:y2,x1:x2],cv2.COLOR_BGR2RGB)
            patch[y1-(yi-r):y2-(yi-r),x1-(xi-r):x2-(xi-r)]=crop
        self.mag_origin=(xi-r,yi-r)
        self.mphoto=ImageTk.PhotoImage(Image.fromarray(patch).resize((self.mag_size,self.mag_size),Image.Resampling.NEAREST))
        self.mag.delete('all');self.mag.create_image(0,0,image=self.mphoto,anchor='nw')
        key=(self.current,self.pt.get().strip())
        xy=self.anchors.get(key,self.cursor_xy)
        mx=(xy[0]-self.mag_origin[0])*self.mag_size/size;my=(xy[1]-self.mag_origin[1])*self.mag_size/size
        if 0<=mx<self.mag_size and 0<=my<self.mag_size:
            self.mag.create_line(mx-15,my,mx+15,my,fill='#00FFFF',width=2)
            self.mag.create_line(mx,my-15,mx,my+15,fill='#00FFFF',width=2)
        self.mag.create_text(5,5,text=f'原图附近：{x:.2f}, {y:.2f} px',fill='white',anchor='nw')

    def mag_click(self,event):
        r=int(self.mag_radius.get());s=2*r+1
        x=self.mag_origin[0]+(event.x+0.5)*s/self.mag_size
        y=self.mag_origin[1]+(event.y+0.5)*s/self.mag_size
        self._capture_position(x,y)

    def start_calibration(self):
        self.calibrating=True;self.scale_points=[]
        self.message.set('比例尺标定：请在同一视频帧上依次点击已知长度标尺的两个端点。然后输入实际长度（毫米）。')

    def _capture_position(self,x,y):
        if not self.calibrating:
            self._store(x,y);return
        if not (0<=x<self.w and 0<=y<self.h):return
        self.scale_points.append((float(x),float(y)))
        if len(self.scale_points)==1:
            self.message.set('已标定第一个端点，请在同一帧点击第二个端点；可先将标尺两端显示在画面里。')
            return
        self.calibrating=False
        start,end=self.scale_points[:2]
        px=float(np.hypot(end[0]-start[0],end[1]-start[1]))
        if px<2:
            messagebox.showwarning('标尺距离过小','两个标尺端点在原图相距不足2像素，无法可靠标定。',parent=self);return
        mm=simpledialog.askfloat('实际标尺长度',f'两点相距 {px:.3f} 原始像素。\n请输入该段标尺的真实长度（mm），需在追踪对象同一运动平面：',parent=self,minvalue=1e-8)
        if mm is None:return
        scale=mm/px
        if self.calibration_callback:self.calibration_callback(scale)
        self.message.set(f'已得到比例尺：{scale:.9g} mm/原图像素。请检查标尺实际长度、同一深度平面和畸变误差。')

    def show_marks(self):
        win=tk.Toplevel(self);win.title('全部人工标点 · 双击跳转相应帧')
        win.geometry('710x450');win.minsize(500,330)
        tk.Label(win,text='逐点人工坐标（可在主画面/高倍镜重新标记，或通过输入框修改）',font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',padx=15,pady=(12,7))
        outer=tk.Frame(win);outer.pack(fill='both',expand=True,padx=12)
        tv=ttk.Treeview(outer,columns=('frame','point','x','y'),show='headings',selectmode='browse')
        for col,title,width in (('frame','帧号',90),('point','点名称',170),('x','X 原图像素',160),('y','Y 原图像素',160)):
            tv.heading(col,text=title);tv.column(col,width=width,anchor='center')
        scroll=ttk.Scrollbar(outer,orient='vertical',command=tv.yview);tv.configure(yscrollcommand=scroll.set)
        tv.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        for (frame,point),(x,y) in sorted(self.anchors.items()):tv.insert('', 'end',values=(frame,point,f'{x:.5f}',f'{y:.5f}'))
        def selected_key():
            selection=tv.selection()
            if not selection:return None
            f,point,*_=tv.item(selection[0],'values')
            return int(f),point
        def jump(_=None):
            key=selected_key()
            if key:
                self.pt.set(key[1]);self.show_frame(key[0]);self.lift()
        def delete():
            key=selected_key()
            if key and key in self.anchors:
                del self.anchors[key]
                tv.delete(tv.selection()[0]);self._render()
        tv.bind('<Double-Button-1>',jump)
        bar=tk.Frame(win);bar.pack(fill='x',padx=13,pady=12)
        tk.Button(bar,text='跳转选中帧',command=jump).pack(side='left',padx=4)
        tk.Button(bar,text='删除选中人工标点',command=delete).pack(side='left',padx=4)
        tk.Button(bar,text='关闭',command=win.destroy).pack(side='right',padx=4)

    def commit_xy(self):
        try:self._store(float(self.xval.get().strip()),float(self.yval.get().strip()))
        except ValueError:messagebox.showerror('坐标格式','X/Y 必须分别填写有效数字（单位为原始视频像素）。',parent=self)

    def mark_retrack_anchor(self):
        """Mark a VERIFIED same-name anchor on this frame.

        This is not an immediate retrack; saving the anchor CSV and rerunning
        video tracking genuinely causes LK to restart at the annotated frame.
        """
        try:
            x=float(self.xval.get());y=float(self.yval.get())
            self._store(x,y)
            if (self.current,self.pt.get().strip()) in self.anchors:
                self.message.set(f'已在第 {self.current} 帧为 {self.pt.get()} 设置人工重追踪锚点。请保存整份锚点CSV，回到【视频追踪】重新点击开始分析；算法会从此帧使用这一坐标继续自动LK跟踪，不会凭空修补之前被遮挡的缺失帧。')
        except (ValueError,TypeError):
            messagebox.showwarning('尚未确定正确位置','请先在当前视频帧用鼠标点击真实位置，或输入 X/Y 原始像素坐标，再点击本按钮。',parent=self)

    def load_auto(self):
        key=(self.current,self.pt.get().strip())
        if key not in self.auto:
            messagebox.showinfo('本帧没有自动记录','当前帧与点名没有自动结果。可以直接在画面上标点。',parent=self);return
        self.xval.set(f'{self.auto[key][0]:.4f}');self.yval.set(f'{self.auto[key][1]:.4f}')
        self.cursor_xy=self.auto[key];self._render_magnifier()

    def nudge(self,dx,dy):
        key=(self.current,self.pt.get().strip())
        if key not in self.anchors:
            messagebox.showinfo('请先选点','先在当前帧手工点击或输入坐标，然后才能微调。',parent=self);return
        x,y=self.anchors[key];self._store(x+dx,y+dy)

    def delete_current(self):
        self.anchors.pop((self.current,self.pt.get().strip()),None)
        self._render();self._update_entries()

    def jump_selected(self,event):
        indices=self.anchor_list.curselection()
        if not indices:return
        keys=sorted(self.anchors)
        k=keys[indices[0]]
        self.pt.set(k[1]);self.show_frame(k[0]);self._update_entries()

    def import_csv(self,path):
        from core.point_tracking import prepare_anchors
        d=prepare_anchors(pd.read_csv(path),self.w,self.h)
        for row in d.itertuples(index=False):self.anchors[(int(row.frame),str(row.point_id))]=(float(row.x_px),float(row.y_px))
        self._render();self.message.set(f'已导入 {len(d)} 条标注，覆盖了相同帧同名点的旧标注。')

    def load_csv(self):
        path=filedialog.askopenfilename(parent=self,title='读取已保存的标点表',filetypes=[('CSV','*.csv')])
        if path:
            try:self.import_csv(path)
            except Exception as exc:messagebox.showerror('标注文件不正确',str(exc),parent=self)

    def save(self):
        if not self.anchors:
            messagebox.showwarning('还没标点','至少为一个实际物理特征标记一个视频帧。',parent=self);return
        path=filedialog.asksaveasfilename(parent=self,title='保存人工标记（可用于追踪锚点或人工修正）',
                        initialfile=self.video.stem+'_人工特征点.csv',defaultextension='.csv',filetypes=[('CSV文件','*.csv')])
        if not path:return
        rows=[dict(frame=k[0],point_id=k[1],x_px=v[0],y_px=v[1]) for k,v in sorted(self.anchors.items())]
        try:
            from core.point_tracking import prepare_anchors
            df=prepare_anchors(pd.DataFrame(rows),self.w,self.h)
            df.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.6f')
            if self.output_callback:self.output_callback(path)
            messagebox.showinfo('标注已保存',f'写入 {len(df)} 条带原始像素坐标的标注：\n{path}\n\n关闭标注器后，回主界面点击「开始分析」。',parent=self)
        except Exception as exc:messagebox.showerror('保存失败',str(exc),parent=self)

    def close(self):
        self.cap.release();self.destroy()
