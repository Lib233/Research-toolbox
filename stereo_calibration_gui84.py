"""Optional non-modal calibration wizard for synchronized stereo pairs."""
import json,threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog,ttk,messagebox
from core.reconstruction3d84 import calibrate_stereo_chessboard


def open_stereo_wizard(owner,on_saved=None):
    win=tk.Toplevel(owner);win.title(' 双相机三维标定 · 棋盘格照片');win.geometry('790x610');win.minsize(620,450)
    win.transient(owner)
    panel=ttk.Frame(win,padding=16);panel.pack(fill='both',expand=True)
    ttk.Label(panel,text='双相机标定（有真实的双摄像机图像后才使用）',font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w',pady=(3,10))
    help_text=('左右两台固定相机，同时拍摄同一块棋盘格。请移动棋盘格到不同距离/倾角，最好15~25对以上。\n'
       '把左右照片放到两个文件夹；每一对照片必须【文件名完全相同】，图像分辨率也必须相同。\n'
       '棋盘格填写的是内部角点数量（不是方块数量）；每格边长必须用尺实际测量，单位 mm。\n'
       '标定完成并不等于三维精度得到保证；还要验证重投影误差、同步和深度敏感性。\n'
       '切勿把同一录像复制两份作为双目视频：那不能恢复三维。')
    ttk.Label(panel,text=help_text,wraplength=710,justify='left').pack(fill='x',pady=(0,14))
    args={}
    for key,caption,default in [('left','左相机棋盘格照片文件夹',''),('right','右相机棋盘格照片文件夹',''),
                                 ('cols','内部角点：每行多少个','9'),('rows','内部角点：每列多少个','6'),
                                 ('size','一个方格的真实边长（mm）','10')]:
        line=ttk.Frame(panel);line.pack(fill='x',pady=5)
        ttk.Label(line,text=caption,width=30).pack(side='left')
        var=tk.StringVar(value=default);args[key]=var
        ttk.Entry(line,textvariable=var).pack(side='left',fill='x',expand=True)
        if key in ('left','right'):
            ttk.Button(line,text='选择文件夹',command=lambda v=var:v.set(filedialog.askdirectory(parent=win))).pack(side='right',padx=6)
    status=tk.StringVar(value='等待填写标定照片与参数。')
    ttk.Label(panel,textvariable=status,wraplength=700,justify='left').pack(anchor='w',pady=(22,9))
    pb=ttk.Progressbar(panel,mode='indeterminate');pb.pack(fill='x')
    buttons=ttk.Frame(panel);buttons.pack(fill='x',pady=16)
    def done(result=None,error=None):
        pb.stop();start.config(state='normal')
        if error:
            status.set('标定失败：'+str(error));messagebox.showerror('标定未完成',str(error),parent=win);return
        status.set(f'识别到 {result["calibration_pairs"]} 对照片；立体标定 RMS={result["rms_stereo_px"]:.3f}px。请独立核实精度。')
        target=filedialog.asksaveasfilename(parent=win,title='保存三维标定参数',initialfile='stereo_calibration.json',defaultextension='.json',filetypes=[('JSON文件','*.json')])
        if target:
            Path(target).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
            if on_saved:on_saved(target)
            messagebox.showinfo('标定文件已保存','标定已保存。下一步分别追踪左右视频，并用此文件三角重建；务必检验误差。',parent=win)
    def start_calibration():
        values={key:v.get().strip() for key,v in args.items()}
        if not all(values.values()):messagebox.showwarning('缺少参数','请完整填写两边照片文件夹及棋盘格参数。',parent=win);return
        start.config(state='disabled');status.set('正在计算：识别角点及联合标定，可能需要数分钟……');pb.start(10)
        def work():
            try:
                result=calibrate_stereo_chessboard(values['left'],values['right'],int(values['cols']),int(values['rows']),float(values['size']))
                win.after(0,lambda:done(result=result))
            except Exception as exc:
                error=str(exc);win.after(0,lambda:done(error=error))
        threading.Thread(target=work,daemon=True).start()
    start=ttk.Button(buttons,text='开始标定并保存 JSON',command=start_calibration)
    start.pack(side='left');ttk.Button(buttons,text='关闭',command=win.destroy).pack(side='right')
    return win
