#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- BIBLIOTERIAS PADRÃO ---
import speech_recognition as sr
from gtts import gTTS
from playsound3 import playsound
import datetime
import os
import time
import ast, operator, re
import math
import tempfile
import webbrowser # Para abrir URLs (ainda útil como fallback ou para a primeira autenticação)

# --- BIBLIOTECAS DE TERCEIROS (FUNCIONALIDADES ADICIONAIS) ---
import requests  # Para Clima e Moedas
from PIL import ImageGrab, Image  # Para Captura de Tela e para OCR (ainda necessário para ImageGrab)
import spotipy # NOVA BIBLIOTECA PARA SPOTIFY
from spotipy.oauth2 import SpotifyOAuth # Para autenticação do Spotify

# Para reconhecimento de imagem e processamento
import cv2
import numpy as np # Adicionado para manipulação de arrays de imagem

# Tente importar pyttsx3 para fala offline (opcional)
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("Biblioteca 'pyttsx3' não encontrada. Fala offline não estará disponível.")


# Tente importar bibliotecas para controle de volume (Windows)
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
    print("Biblioteca 'pycaw' não encontrada. Controle de volume não estará disponível.")


# Para reconhecimento facial
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
    print("Biblioteca 'face_recognition' encontrada.")
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("Biblioteca 'face_recognition' não encontrada. Reconhecimento facial não estará disponível.")

# Para OCR (Reconhecimento de Texto) com EasyOCR
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    print("Biblioteca 'easyocr' encontrada.")
    # Inicialize o leitor EasyOCR uma vez para reutilização
    # 'en' para inglês, 'pt' para português. Adicione outros idiomas conforme necessário.
    reader = easyocr.Reader(['en', 'pt']) # Carrega modelos para inglês e português
    print("EasyOCR reader inicializado.")
except ImportError:
    EASYOCR_AVAILABLE = False
    print("Biblioteca 'easyocr' não encontrada. Reconhecimento de letras (OCR) não estará disponível.")
except Exception as e:
    EASYOCR_AVAILABLE = False
    print(f"Erro ao inicializar EasyOCR: {e}. Reconhecimento de letras (OCR) não estará disponível.")


# --- CONFIGURAÇÕES E CONSTANTES ---

# Chave da API de Clima (OpenWeatherMap)
WEATHER_API_KEY = "6c4225d77eacd90feb7e27cb612c9741"

# Mapeamento de Moedas para a API de Cotação
CURRENCY_MAP = {
    "dólar": {"code": "USD", "name": "Dólar Americano"},
    "dólares": {"code": "USD", "name": "Dólar Americano"},
    "dólar americano": {"code": "USD", "name": "Dólar Americano"},
    "euro": {"code": "EUR", "name": "Euro"},
    "euros": {"code": "EUR", "name": "Euro"},
    "bitcoin": {"code": "BTC", "name": "Bitcoin"}
}

# Setup de arquivos
os.makedirs('data', exist_ok=True)
AGENDA_FILE = os.path.join('data', 'agenda.txt')
if not os.path.exists(AGENDA_FILE):
    open(AGENDA_FILE, 'w', encoding='utf-8').close()

# --- CONFIGURAÇÕES DO SPOTIFY ---
os.environ['SPOTIPY_CLIENT_ID'] = 'd2029dbe36b7479fbb1b4768e3d5246e'
os.environ['SPOTIPY_CLIENT_SECRET'] = '76034efe75da40c78b81fdaed161e9ff'
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://127.0.0.1:8888/callback'

SCOPE = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing"

sp = None # Variável global para a instância do Spotipy
def authenticate_spotify():
    global sp
    try:
        auth_manager = SpotifyOAuth(scope=SCOPE, cache_path=".spotify_token_cache")
        sp = spotipy.Spotify(auth_manager=auth_manager)
        speak("Conectado ao Spotify.")
    except Exception as e:
        print(f"Erro ao autenticar com Spotify: {e}")
        speak("Não consegui conectar ao Spotify. Verifique suas credenciais e permissões.")
        sp = None # Garante que sp seja None em caso de falha

# --- INICIALIZAÇÃO OTIMIZADA DO MICROFONE ---
r = sr.Recognizer()
try:
    with sr.Microphone() as source:
        print("Calibrando o microfone para o ruído ambiente, por favor aguarde...")
        r.adjust_for_ambient_noise(source, duration=1.5)
        print("Microfone calibrado.")
except Exception as e:
    print(f"Não foi possível inicializar o microfone: {e}")
    print("Funcionalidades de voz podem não funcionar.")

# --- FUNÇÕES DE FALA E ESCUTA ---

def speak(text, lang='pt'):
    print(f"[SPEAK ONLINE - {lang.upper()}]", text)
    try:
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            filename = fp.name
        tts.save(filename)
        playsound(filename)
        os.remove(filename)
    except Exception as e:
        print(f"Erro no gTTS: {e}. Tentando fala offline.")
        speak_offline(text)

def speak_offline(text):
    if not PYTTSX3_AVAILABLE:
        print("Biblioteca pyttsx3 não encontrada. Impossível usar fala offline.")
        return
    print("[SPEAK OFFLINE]", text)
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for voice in voices:
        if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
            engine.setProperty('voice', voice.id)
            break
    engine.say(text)
    engine.runAndWait()

def listen(timeout=5, phrase_time_limit=6):
    with sr.Microphone() as source:
        try:
            print("Ouvindo...")
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            print("Reconhecendo...")
            return r.recognize_google(audio, language='pt-BR').lower()
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            print("Não entendi o que você disse.")
            return ""
        except sr.RequestError as e:
            print(f"Erro no serviço de reconhecimento; {e}")
            return ""
        except Exception as e:
            print(f"Erro na escuta: {e}")
            return ""

# --- FUNÇÕES DE COMANDOS ---

def add_event(text):
    data_cadastro = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(AGENDA_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{data_cadastro}] Evento: {text}\n")
    speak("Evento cadastrado.")

def read_agenda():
    with open(AGENDA_FILE, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        speak("Sua agenda está vazia.")
        return
    speak(f"Você tem {len(lines)} eventos na agenda.")
    for ln in lines:
        print(ln)
        speak(ln)
        time.sleep(0.3)

def clear_agenda():
    open(AGENDA_FILE, 'w', encoding='utf-8').close()
    speak("Agenda limpa.")

def safe_eval(expr):
    expr = expr.lower()
    expr = re.sub(r'\b(x|vezes)\b', '*', expr)
    expr = re.sub(r'\b(mais)\b', '+', expr)
    expr = re.sub(r'\b(menos)\b', '-', expr)
    expr = re.sub(r'\b(dividido por|dividido|por)\b', '/', expr)
    expr = expr.replace(',', '.')
    expr = re.sub(r'[^0-9+\-*/().^sqrt ]','',expr)
    expr = expr.replace("^", "**")
    if "sqrt" in expr:
        try:
            num = float(expr.replace("sqrt", "").strip("() "))
            return math.sqrt(num)
        except: raise ValueError("Expressão de raiz inválida")
    if not any(c in expr for c in "+-*/"):
        raise ValueError("Expressão incompleta")
    node = ast.parse(expr, mode='eval')
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}
    def _eval(n):
        if isinstance(n, ast.Expression): return _eval(n.body)
        if isinstance(n, ast.BinOp): return ops[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -_eval(n.operand)
        if isinstance(n, ast.Constant): return n.value
        raise ValueError("Expressão inválida")
    return _eval(node)

def resolver_equacao(text):
    def get_coefficient(name):
        speak(f"Qual o valor de {name}?")
        while True:
            try:
                coeff_str = listen(timeout=6, phrase_time_limit=5)
                if coeff_str: return float(coeff_str.replace(',', '.'))
                else: speak("Não ouvi o número, por favor, repita.")
            except (ValueError, TypeError):
                speak("Não entendi. Por favor, diga apenas o número.")
    if "primeiro grau" in text:
        a, b = get_coefficient("A"), get_coefficient("B")
        if a == 0: return speak("O coeficiente 'a' não pode ser zero.")
        speak(f"A raiz da equação é x = {-b / a:.2f}")
    elif "segundo grau" in text:
        a, b, c = get_coefficient("A"), get_coefficient("B"), get_coefficient("C")
        if a == 0: return speak("O coeficiente 'a' não pode ser zero.")
        delta = (b**2) - (4*a*c)
        if delta < 0: speak(f"A equação não possui raízes reais, pois o delta é negativo, valendo {delta:.2f}.")
        elif delta == 0: speak(f"A equação possui uma raiz real: x = {-b / (2*a):.2f}")
        else: speak(f"A equação possui duas raízes reais. X1 é igual a {(-b + math.sqrt(delta)) / (2*a):.2f}, e X2 é igual a {(-b - math.sqrt(delta)) / (2*a):.2f}")
    else:
        speak("Não entendi o tipo de equação.")

def get_weather(city):
    params = {"q": city, "appid": WEATHER_API_KEY, "lang": "pt_br", "units": "metric"}
    try:
        response = requests.get("http://api.openweathermap.org/data/2.5/weather", params=params)
        if response.status_code != 200:
            return "Não consegui obter a previsão para essa cidade."
        data = response.json()
        forecast = f"A temperatura em {data['name']} é de {data['main']['temp']:.0f} graus Celsius, com {data['weather'][0]['description']}."
        return forecast
    except Exception as e:
        print("Erro ao obter clima:", e)
        return "Desculpe, ocorreu um erro ao buscar a previsão do tempo."

def get_currency_rate(currency_code, currency_name):
    url = f"https://economia.awesomeapi.com.br/json/last/{currency_code}-BRL"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return f"Não consegui obter a cotação para {currency_name}."
        data = response.json()
        value = float(data[f"{currency_code}BRL"]['bid'])
        if currency_code == 'BTC':
            return f"A cotação do {currency_name} é de {value:,.2f} reais.".replace(",", ".")
        else:
            reais, centavos = int(value), int((value - int(value)) * 100)
            return f"A cotação do {currency_name} é de {reais} reais e {centavos} centavos."
    except Exception as e:
        print(f"Erro ao buscar cotação: {e}")
        return "Ocorreu um erro ao buscar a cotação."

def take_screenshot():
    try:
        screenshot_dir = 'screenshots'
        os.makedirs(screenshot_dir, exist_ok=True)
        filename = f"captura_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
        filepath = os.path.join(screenshot_dir, filename)
        ImageGrab.grab().save(filepath)
        return f"Captura de tela salva como {filename}"
    except Exception as e:
        print(f"Erro ao capturar a tela: {e}")
        return "Desculpe, não consegui capturar a tela."

def change_volume(amount):
    if not PYCAW_AVAILABLE: return "Desculpe, a biblioteca para controlar o volume não está instalada."
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        new_volume = max(0.0, min(1.0, volume.GetMasterVolumeLevelScalar() + amount))
        volume.SetMasterVolumeLevelScalar(new_volume, None)
        return f"Volume ajustado para {int(new_volume * 100)}%"
    except Exception as e:
        print(f"Erro ao alterar o volume: {e}")
        return "Ocorreu um erro ao ajustar o volume."

def set_volume(level_percent):
    if not PYCAW_AVAILABLE: return "Desculpe, a biblioteca para controlar o volume não está instalada."
    if not 0 <= level_percent <= 100: return "Por favor, diga um número entre 0 e 100."
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level_percent / 100.0, None)
        return f"Volume ajustado para {level_percent}%"
    except Exception as e:
        print(f"Erro ao definir o volume: {e}")
        return "Ocorreu um erro ao definir o volume."

# --- FUNÇÃO PARA TOCAR MÚSICA NO SPOTIFY VIA API ---
def play_spotify_music_api(music_name):
    global sp
    if sp is None:
        speak("Tentando conectar ao Spotify para tocar a música.")
        authenticate_spotify()
        if sp is None: # Se a autenticação falhar
            return speak("Não consegui autenticar com o Spotify. A reprodução não pode continuar.")

    try:
        results = sp.search(q=music_name, type='track', limit=1)
        if not results['tracks']['items']:
            return speak(f"Não encontrei a música {music_name} no Spotify.")

        track_uri = results['tracks']['items'][0]['uri']
        track_name = results['tracks']['items'][0]['name']
        artist_name = results['tracks']['items'][0]['artists'][0]['name']

        devices = sp.devices()
        active_device_id = None
        for device in devices['devices']:
            if device['is_active']:
                active_device_id = device['id']
                break
        
        if active_device_id:
            sp.start_playback(device_id=active_device_id, uris=[track_uri])
            speak(f"Tocando {track_name} de {artist_name} no Spotify.")
        else:
            if devices['devices']:
                speak("Nenhum dispositivo Spotify ativo. Tentando iniciar no primeiro dispositivo encontrado.")
                first_device_id = devices['devices'][0]['id']
                sp.transfer_playback(device_id=first_device_id, force_play=True)
                time.sleep(1)
                sp.start_playback(device_id=first_device_id, uris=[track_uri])
                speak(f"Tocando {track_name} de {artist_name} no Spotify.")
            else:
                speak("Não encontrei nenhum dispositivo Spotify para tocar a música. Por favor, abra o Spotify em algum lugar.")
                webbrowser.open(f"https://open.spotify.com/search/{music_name.replace(' ', '%20')}")

    except spotipy.exceptions.SpotifyException as se:
        print(f"Erro do Spotify API: {se}")
        if "Authentication failed" in str(se):
            speak("Sua sessão do Spotify expirou ou está inválida. Por favor, autentique novamente.")
            if os.path.exists(".spotify_token_cache"):
                os.remove(".spotify_token_cache")
            sp = None
        else:
            speak("Ocorreu um erro com o Spotify. Verifique se o Spotify está aberto.")
    except Exception as e:
        print(f"Erro ao tocar música no Spotify: {e}")
        speak("Desculpe, ocorreu um erro inesperado ao tentar tocar a música no Spotify.")

# --- NOVA FUNÇÃO PARA ABRIR VÍDEOS DO YOUTUBE ---
def open_youtube_video(query):
    if not query:
        return speak("Por favor, diga o que você gostaria de procurar no YouTube.")
    
    search_query = query.replace(' ', '+')
    youtube_url = f"https://www.youtube.com/results?search_query={search_query}"
    
    speak(f"Abrindo YouTube com a pesquisa por {query}.")
    try:
        webbrowser.open(youtube_url)
    except Exception as e:
        print(f"Erro ao abrir o navegador para o YouTube: {e}")
        speak("Desculpe, não consegui abrir o YouTube no seu navegador.")


# --- NOVAS FUNÇÕES DE RECONHECIMENTO DE IMAGEM ---

# Função para carregar e codificar faces conhecidas
known_face_encodings = []
known_face_names = []

def load_known_faces():
    global known_face_encodings, known_face_names
    known_face_encodings = [] # Limpa as listas antes de carregar novamente
    known_face_names = []

    faces_dir = 'faces'
    os.makedirs(faces_dir, exist_ok=True)

    if not os.listdir(faces_dir):
        speak("Nenhuma face conhecida encontrada. Por favor, adicione imagens de pessoas no diretório 'faces'.")
        return

    speak("Carregando faces conhecidas...")
    for filename in os.listdir(faces_dir):
        if filename.lower().endswith((".jpg", ".png", ".jpeg")):
            try:
                name = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title() # Formata o nome
                image_path = os.path.join(faces_dir, filename)
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    known_face_encodings.append(encodings[0])
                    known_face_names.append(name)
                    print(f"Face de '{name}' carregada.")
                else:
                    print(f"Não foi possível encontrar face em '{filename}'.")
            except Exception as e:
                print(f"Erro ao carregar face '{filename}': {e}")
    
    if known_face_names:
        speak(f"Carreguei {len(known_face_names)} faces conhecidas.")
    else:
        speak("Não consegui carregar nenhuma face conhecida.")

# Carregar faces ao iniciar, se a biblioteca estiver disponível
if FACE_RECOGNITION_AVAILABLE:
    load_known_faces()

def recognize_face():
    if not FACE_RECOGNITION_AVAILABLE:
        return speak("Desculpe, a biblioteca 'face_recognition' não está instalada ou configurada.")
    
    # Se ainda não houver faces, tenta carregar novamente
    if not known_face_names:
        speak("Nenhuma face conhecida para comparar. Tentando carregar novamente.")
        load_known_faces()
        if not known_face_names:
            return speak("Ainda não consegui carregar nenhuma face conhecida. Certifique-se de que há imagens no diretório 'faces'.")

    speak("Abrindo a câmera para reconhecimento facial. Pressione 'q' para sair.")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return speak("Não consegui acessar a câmera para reconhecimento facial. Verifique se ela está conectada e não está em uso.")

    process_this_frame = True
    last_spoken_name = ""
    last_speak_time = time.time()
    SPEAK_INTERVAL = 3 # Falar a cada 3 segundos se a mesma pessoa for detectada

    while True:
        ret, frame = cap.read()
        if not ret:
            speak("Falha ao capturar imagem da câmera.")
            break

        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = small_frame[:, :, ::-1] # Converte de BGR para RGB

        face_locations = []
        face_encodings = []
        face_names = []

        if process_this_frame:
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                name = "Desconhecido"

                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                if len(face_distances) > 0: # Garante que há distâncias para comparar
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = known_face_names[best_match_index]
                
                face_names.append(name)
                
                # Feedback de voz
                if name != "Desconhecido" and (name != last_spoken_name or (time.time() - last_speak_time > SPEAK_INTERVAL)):
                    speak(f"Olá, {name}.")
                    last_spoken_name = name
                    last_speak_time = time.time()
                elif name == "Desconhecido" and (name != last_spoken_name or (time.time() - last_speak_time > SPEAK_INTERVAL)):
                    speak("Reconheci uma face desconhecida.")
                    last_spoken_name = name
                    last_speak_time = time.time()

        process_this_frame = not process_this_frame

        for (top, right, bottom, left), name in zip(face_locations, face_names):
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            color = (0, 0, 255) if name == "Desconhecido" else (0, 255, 0) # Vermelho para desconhecido, verde para conhecido
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

        cv2.imshow('Reconhecimento Facial', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    speak("Reconhecimento facial encerrado.")


def recognize_text():
    global reader # Acessa o leitor EasyOCR globalmente
    if not EASYOCR_AVAILABLE:
        return speak("Desculpe, a biblioteca 'easyocr' não está instalada ou configurada corretamente.")

    speak("Abrindo a câmera para reconhecimento de letras. Pressione 'q' para sair.")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return speak("Não consegui acessar a câmera para reconhecimento de letras. Verifique se ela está conectada e não está em uso.")
    
    last_spoken_text = ""
    last_speak_time = time.time()
    SPEAK_INTERVAL = 5 # Falar a cada 5 segundos se o texto mudar significativamente

    while True:
        ret, frame = cap.read()
        if not ret:
            speak("Falha ao capturar imagem da câmera.")
            break

        # EasyOCR prefere imagens diretamente do OpenCV (BGR ou RGB)
        # Não precisa converter para escala de cinza ou PIL Image especificamente para o EasyOCR,
        # ele lida com isso internamente.

        try:
            # Usar o reader para reconhecer texto no frame
            # O resultado é uma lista de tuplas: (bbox, text, confidence)
            results = reader.readtext(frame, detail=0, paragraph=True) # detail=0 retorna apenas o texto, paragraph=True tenta agrupar linhas

            clean_text = ' '.join(results).strip() # Junta todos os textos reconhecidos

            if clean_text:
                # Desenhar o texto na tela para feedback visual (opcional)
                cv2.putText(frame, clean_text[:50], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Lógica para falar apenas quando o texto for novo ou significativo
                if clean_text != last_spoken_text and \
                   (time.time() - last_speak_time > SPEAK_INTERVAL or \
                    len(set(clean_text.split()) - set(last_spoken_text.split())) > 2):
                    
                    print("Texto reconhecido:", clean_text)
                    speak(f"Reconheci o texto: {clean_text[:50]}...") # Limita a fala para não ser muito longa
                    last_spoken_text = clean_text
                    last_speak_time = time.time()
            else:
                 cv2.putText(frame, "Nenhum texto detectado", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        except Exception as e:
            print(f"Erro ao reconhecer texto com EasyOCR: {e}")
            cv2.putText(frame, "Erro no EasyOCR", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow('Reconhecimento de Letras (EasyOCR)', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    speak("Reconhecimento de letras encerrado.")

# Para reconhecimento de objetos/animais, usaremos detecção de objetos YOLOv3 com OpenCV
# --- CONFIGURAÇÃO YOLOv3 ---
# Verifique se os arquivos do modelo YOLOv3 (weights, config, names) estão na pasta 'yolo_model'

coco_names = []
net = None
YOLO_AVAILABLE = False

# Cria o diretório 'yolo_model' se não existir
os.makedirs('yolo_model', exist_ok=True)

# Verifica se os arquivos do modelo existem
yolo_weights_path = 'yolo_model/yolov3.weights'
yolo_config_path = 'yolo_model/yolov3.cfg'
coco_names_path = 'yolo_model/coco.names'

if not (os.path.exists(yolo_weights_path) and os.path.exists(yolo_config_path) and os.path.exists(coco_names_path)):
    print("\nAVISO: Arquivos do modelo YOLOv3 não encontrados na pasta 'yolo_model'.")
    print("Para reconhecimento de objetos, baixe os arquivos:")
    print(f"  - {yolo_weights_path} (grande, ~240MB): https://pjreddie.com/media/files/yolov3.weights")
    print(f"  - {yolo_config_path}: https://github.com/pjreddie/darknet/blob/master/cfg/yolov3.cfg")
    print(f"  - {coco_names_path}: https://github.com/pjreddie/darknet/blob/master/data/coco.names")
    print("Coloque-os na pasta 'yolo_model'. Reconhecimento de objetos estará desativado por enquanto.\n")
else:
    try:
        with open(coco_names_path, 'r') as f:
            coco_names = [line.strip() for line in f.readlines()]
        net = cv2.dnn.readNet(yolo_weights_path, yolo_config_path)
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU) # Pode mudar para DNN_TARGET_CUDA para GPU se tiver uma
        YOLO_AVAILABLE = True
        print("Modelo YOLOv3 carregado com sucesso.")
    except Exception as e:
        print(f"Erro ao carregar o modelo YOLOv3 ou 'coco.names': {e}")
        print("Verifique se os arquivos estão corretos e o OpenCV está funcionando.")
        YOLO_AVAILABLE = False


def recognize_objects():
    if not YOLO_AVAILABLE:
        return speak("Desculpe, os arquivos do modelo YOLOv3 não foram encontrados ou carregados corretamente. Por favor, verifique a pasta 'yolo_model'.")

    speak("Abrindo a câmera para reconhecimento de objetos e animais. Pressione 'q' para sair.")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return speak("Não consegui acessar a câmera para reconhecimento de objetos. Verifique se ela está conectada e não está em uso.")

    layer_names = net.getLayerNames()
    # Pega os nomes das camadas de saída para o YOLO
    output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    
    last_spoken_objects = set()
    last_speak_time = time.time()
    SPEAK_INTERVAL = 5 # Falar a cada 5 segundos se houver novos objetos ou mudança

    while True:
        ret, frame = cap.read()
        if not ret:
            speak("Falha ao capturar imagem da câmera.")
            break

        height, width, channels = frame.shape

        blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
        net.setInput(blob)
        outs = net.forward(output_layers)

        class_ids = []
        confidences = []
        boxes = []
        current_objects_detected = set()

        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > 0.5: # Limite de confiança
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)

                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)

                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)
                    
                    if class_id < len(coco_names): # Garante que o ID da classe é válido
                        current_objects_detected.add(coco_names[class_id])
