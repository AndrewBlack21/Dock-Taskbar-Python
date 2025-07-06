import os, json, subprocess, ctypes, configparser
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from PIL import Image, ImageTk
import win32gui, win32con, win32api, win32ui, win32event, winerror
from win32com.client import Dispatch
import sys


# ——————————————————————————————————————
# Manter a aplicação numa instancia unica
# --------------------------------------
MUTEX_NAME = "MinhaDockUnicaAplicacaoMutex_1A2B3C4D"
APP_WINDOW_TITLE = "MinhaDockAplicacaoUnicaJanela"
# --------------------------------------

# ——————————————————————————————————————
# Variavel para fechar a Dock sozinho
AUTO_HIDE_DELAY_MS = 10000  # 10 segundos

# ——————————————————————————————————————

# ——————————————————————————————————————
#  Configurações e persistência
# ——————————————————————————————————————

if hasattr(sys, '_MEIPASS'):
    PASTA = sys._MEIPASS # Diretório temporário do executável
else:
    PASTA = os.path.dirname(__file__) # Diretório normal do script Python

DB    = os.path.join(PASTA, "atalhos.json")
FALL  = os.path.join(PASTA, "default_icon.ico")

# ——————————————————————————————————————
#  Carrega os atalhos do arquivo JSON
# ——————————————————————————————————————
def carregar_atalhos():
  if os.path.exists(DB):
    with open(DB, "r", encoding="utf-8") as f:
      return json.load(f)
  return []

# ————————————————————————————————————
#  Salva os atalhos no arquivo JSON
# ——————————————————————————————————————

def salvar_atalhos():
  with open(DB, "w", encoding="utf-8") as f:
    json.dump(atalhos, f, indent=2, ensure_ascii=False)

# ——————————————————————————————————————
#  Helpers de atalho / .url
# ——————————————————————————————————————

def resolve_lnk(path):
  sh = Dispatch("WScript.Shell")
  sc = sh.CreateShortcut(path)
  return sc.Targetpath

def resolve_url_icon(path):
  cfg = configparser.ConfigParser()
  try:
    cfg.read(path, encoding="utf-8")
    icon = cfg.get("InternetShortcut", "IconFile", fallback=None)
    return icon.split(",",1)[0] if icon else None
  except:
    return None

# ——————————————————————————————————————
#  Extração de ícone de executável via GDI
# ——————————————————————————————————————

def extract_exe_icon(path):
  large, small = win32gui.ExtractIconEx(path, 0)
  handles = large + small
  if not handles:
    return None
  hicon = handles[0]

  ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
  ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)

  # DC de tela e DC de memória
  hdc_screen = win32gui.GetDC(0)
  dc_screen  = win32ui.CreateDCFromHandle(hdc_screen)
  dc_mem     = dc_screen.CreateCompatibleDC()

  # bitmap compatível
  bmp = win32ui.CreateBitmap()
  bmp.CreateCompatibleBitmap(dc_screen, ico_x, ico_y)
  dc_mem.SelectObject(bmp)

  # desenha o ícone
  win32gui.DrawIconEx(
    dc_mem.GetSafeHdc(), 0, 0,
    hicon, ico_x, ico_y, 0, 0, win32con.DI_NORMAL
  )

  # ------------------------------
  # extrai bits para PIL
  bmpinfo = bmp.GetInfo()
  bmpstr  = bmp.GetBitmapBits(True)
  img = Image.frombuffer(
    'RGBA',
    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
    bmpstr, 'raw', 'BGRA', 0, 1
  )
  # ------------------------------

  # ------------------------------
  # limpeza correta:
  win32gui.DestroyIcon(hicon)
  dc_mem.DeleteDC()
  dc_screen.DeleteDC()
  win32gui.ReleaseDC(0, hdc_screen)
  win32gui.DeleteObject(bmp.GetHandle())

  return img
  # ------------------------------

# ——————————————————————————————————————
#  Carrega PhotoImage de qualquer fonte
# ——————————————————————————————————————

def obter_imagem_icone(caminho, size=48):
  """
  Tenta extrair um PhotoImage para .ico, .lnk, .exe, .url
  e faz fallback pro default_icon.ico.
  """
  caminho = caminho.replace('/', '\\')
  img = None
  ext = caminho.lower()

  if ext.endswith(".ico") and os.path.exists(caminho):
    img = Image.open(caminho)

  elif ext.endswith(".url"):
    # Lógica para .url que estava faltando
    icon_path = resolve_url_icon(caminho)
    if icon_path and os.path.exists(icon_path):
      if icon_path.lower().endswith((".exe", ".dll")):
        img = extract_exe_icon(icon_path)
      elif icon_path.lower().endswith(".ico"):
        img = Image.open(icon_path)

  elif ext.endswith(".lnk"):
    target = resolve_lnk(caminho)
    if target and os.path.exists(target):
      img = extract_exe_icon(target)

  elif ext.endswith(".exe") and os.path.exists(caminho):
    img = extract_exe_icon(caminho)

  # fallback genérico
  if img is None and os.path.exists(FALL):
    img = Image.open(FALL)

  if img is None:
    return None

  # redimensiona e converte
  img = img.resize((size, size), Image.Resampling.LANCZOS)
  return ImageTk.PhotoImage(img)

# ——————————————————————————————————————
#  Ações: adicionar, remover, abrir
# ——————————————————————————————————————

def adicionar_atalho():
  # root.withdraw()
  arq = filedialog.askopenfilename(
    title="Escolha atalho ou executável",
    filetypes=[
      ("Tudo", ("*.lnk","*.url","*.exe","*.bat","*.cmd","*.ico")),
      ("Todos os arquivos", "*.*")
    ]
  )
  # root.deiconify()
  if not arq: return
  if arq in atalhos:
    messagebox.showinfo("Info", "Atalho já existe.")
    return
  atalhos.append(arq)
  salvar_atalhos()
  montar_dock()

# ------------------------------
# Remove um atalho selecionado
def remover_atalho():
  if not atalhos:
    messagebox.showinfo("Info", "Nenhum atalho para remover.")
    return
  
  #Cria lista de opção para o usuario
  opcao_remover = []
  for i, atalho_path in enumerate(atalhos):
    nome_atalho = atalho_path.split('/')[-1] # Pega o nome do arquivo
    opcao_remover.append(f"{i+1}. {nome_atalho}")
  
  #Exibe uma caixa de dialogo para o usuario escolher o atalho a remover
  # Esta é uma forma simples Para interfaces mais complexas, use um TOplevel ou lista
  escolha = simpledialog.askstring(
    "Remover atalho",
    "Escolha o número do atalho a remover:\n" + "\n".join(opcao_remover)
  )

  if escolha is None: #Usuario cancelou
    return
  
  try:
    indice_selecionado = int(escolha) - 1
    if 0 <= indice_selecionado < len(atalhos):
      atalho_removido = atalhos.pop(indice_selecionado)
      salvar_atalhos()
      montar_dock()
      messagebox.showinfo("Info", f"Atalho : {atalho_removido.split('/')[-1]} removido")
    else:
      messagebox.showerror("Erro", "Número inválido.")
  except ValueError:
    messagebox.showerror("Erro", "Entrada inválida. Por favor, insira um número.")
# ------------------------------

# ------------------------------
# Abre o aplicativo ou atalho
def abrir_aplicativo(path):
  try:
    subprocess.Popen(path, shell=True)
    root.destroy()  # Esconde a dock após abrir o aplicativo
  except Exception as e:
    messagebox.showerror("Erro", f"Não foi possível abrir:\n{path}\n\n{e}")
# ------------------------------

# ——————————————————————————————————————
# Controle de exibição da dock
#----------------------------------------
def show_dock():
  root.deiconify()
  montar_dock()

  cancel_hide_delay() # Cancela qualquer ocultação agendada

# ——————————————————————————————————————
# Delay da dock
#-----------------------------------------

def hide_dock_after_delay():
  global hide_job_id
  cancel_hide_delay()  # Cancela qualquer ocultação agendada
  hide_job_id = root.after(AUTO_HIDE_DELAY_MS, root.destroy)
#------------------------------------------

# ——————————————————————————————————————
# Cancelamento da dock
#------------------------------------------
def cancel_hide_delay():
  global hide_job_id
  if hide_job_id:
    root.after_cancel(hide_job_id)
    hide_job_id = None
#------------------------------------------

# ——————————————————————————————————————
#Nova constante 
#Dimesao da dock e pixel
TASKBAR_HEIGHT_APPROX = 40

#Padding extra entre a dock e a barra de tarefas
DOCK_BOTTOM_OFFSET = 10
# ——————————————————————————————————————

# ——————————————————————————————————————
#  Monta o dock
# ——————————————————————————————————————
def montar_dock():
  for w in dock_frame.winfo_children():
    w.destroy()

  if not atalhos:
    lbl_empty = tk.Label(dock_frame, text="(vazio)", fg="gray", bg="#222222")
    lbl_empty.pack(side=tk.LEFT, padx=8, pady=8)

    lbl_empty.bind("<Enter>", lambda e: cancel_hide_delay())
    lbl_empty.bind("<Leave>", lambda e: hide_dock_after_delay())

  else:
    for path in atalhos:
      ic = obter_imagem_icone(path)
      if ic:
        btn = tk.Button(
          dock_frame, image=ic, bd=0, bg="#222222",
          activebackground="#222222",
          command=lambda p=path: abrir_aplicativo(p)
        )
        btn.image = ic
      else:
        nome = os.path.basename(path)
        btn = tk.Button(
          dock_frame, text=nome, fg="white", bg="#444444", bd=0,
          command=lambda p=path: abrir_aplicativo(p),
          wraplength=80, justify="center"
        )
      btn.pack(side=tk.LEFT, padx=6)  # Este pack está correto aqui

      btn.bind("<Enter>", lambda e: cancel_hide_delay())
      btn.bind("<Leave>", lambda e: hide_dock_after_delay())
      
  # mouse pode estar sobre o frame mas não sobre um botão específico
  dock_frame.bind("<Enter>", lambda e: cancel_hide_delay())
  dock_frame.bind("<Leave>", lambda e: hide_dock_after_delay())

  # O frame ctl (onde ficam os botoes +/-) tambem precisa desses binds
  ctl.bind("<Enter>", lambda e: cancel_hide_delay())
  ctl.bind("<Leave>", lambda e: hide_dock_after_delay())

  # --- INÍCIO DO BLOCO DE DIMENSIONAMENTO (este está correto aqui) ---
  # FORÇA o Tkinter a calcular as dimensões reais dos widgets recém-criados
  root.update_idletasks()

  # Obtém as dimensões da tela
  screen_width = root.winfo_screenwidth()
  screen_height = root.winfo_screenheight()

  # Obtém as dimensões atuais da janela da dock (root).
  current_dock_window_width = root.winfo_width()
  current_dock_window_height = root.winfo_height()

  # Calcula a posição X para centralizar horizontalmente
  x_pos = (screen_width - current_dock_window_width) // 2

  # Calcula a posição Y para ficar acima da barra de tarefas
  y_pos = screen_height - current_dock_window_height - TASKBAR_HEIGHT_APPROX - DOCK_BOTTOM_OFFSET

  # Aplica a nova geometria à janela principal (root)
  root.geometry(f"{current_dock_window_width}x{current_dock_window_height}+{x_pos}+{y_pos}")

  root.update()
# ------------------------------

# ——————————————————————————————————————
#  Setup e mainloop
# ——————————————————————————————————————

if __name__ == "__main__":
  # Declaramos global para garantir que o handle do mutex não seja liberado prematuramente
  global mutex_handle
  mutex_handle = win32event.CreateMutex(None, 1, MUTEX_NAME)
  
  # Obtém o último erro do sistema para verificar se o mutex já existia
  last_error = win32api.GetLastError()

  if last_error == winerror.ERROR_ALREADY_EXISTS:
    # Outra instância já está rodando
    try:
      # Tenta encontrar a janela da instância existente pelo título único.
      # É CRUCIAL que a instância principal defina esse título (verá abaixo).
      hwnd_existing = win32gui.FindWindow(None, APP_WINDOW_TITLE)
      
      if hwnd_existing:
        # Se a janela foi encontrada:
        # 1. Restaura a janela se estiver minimizada
        if win32gui.IsIconic(hwnd_existing):
          win32gui.ShowWindow(hwnd_existing, win32con.SW_RESTORE)
        
        # 2. Garante que a janela esteja visível (importante para docks escondidas)
        win32gui.ShowWindow(hwnd_existing, win32con.SW_SHOW) # SW_SHOW força a exibição
        
        # 3. Traz a janela para o primeiro plano e dá o foco
        win32gui.SetForegroundWindow(hwnd_existing)
        
      # Fecha o handle do mutex que foi criado por ESTA nova instância.
      # Isso é importante para não deixar handles abertos desnecessariamente.
      win32api.CloseHandle(mutex_handle)
      
      # Sai da nova instância, pois a existente já está sendo usada.
      sys.exit() 
      
    except Exception as e:
      print(f"Erro ao tentar trazer instância existente para a frente: {e}")
      win32api.CloseHandle(mutex_handle)
      sys.exit()
      
  # carrega persistência
  atalhos = carregar_atalhos()
  hide_job_id = None

  root = tk.Tk()
  root.overrideredirect(True)
  root.attributes("-topmost", True)
  root.attributes("-alpha", 0.95)
  root.configure(bg="#222222")

  # esconde da taskbar
  hwnd   = ctypes.windll.user32.GetParent(root.winfo_id())
  ex     = ctypes.windll.user32.GetWindowLongPtrW(hwnd, -20)
  ctypes.windll.user32.SetWindowLongPtrW(hwnd, -20, (ex|0x80)&~0x40000)

  dock_frame = tk.Frame(root, bg="#222222")
  dock_frame.pack(padx=10, pady=(10,0))

  ctl = tk.Frame(root, bg="#222222")
  ctl.pack(pady=(0,10))

  tk.Button(ctl, text="+",  fg="white", bg="#333", bd=0, width=2,
      command=adicionar_atalho).pack(side=tk.LEFT, padx=4)
  tk.Button(ctl, text="-",  fg="white", bg="#333", bd=0, width=2,
      command=remover_atalho).pack(side=tk.LEFT)
  tk.Button(ctl, text="X", fg="white", bg="#8B0000", bd=0, width=2,
         command=root.destroy).pack(side=tk.RIGHT, padx=4)
  
  # ctl = tk.Frame(root, bg="#222222")
  # ctl.pack(pady=(0,10))

  
  montar_dock()

  hide_dock_after_delay()  # Inicia o timer para esconder a dock

  root.mainloop()
