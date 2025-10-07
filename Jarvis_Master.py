#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- BIBLIOTECAS PADRÃO ---
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
import datetime
import os
import time
import ast, operator, re
import math
import tempfile
import webbrowser # Para abrir URLs (ainda útil como fallback ou para a primeira autenticação)

# --- BIBLIOTECAS DE TERCEIROS (FUNCIONALIDADES ADICIONAIS) ---
import requests  # Para Clima e Moedas
from PIL import ImageGrab  # Para Captura de Tela
import spotipy # NOVA BIBLIOTECA PARA SPOTIFY
from spotipy.oauth2 import SpotifyOAuth # Para autenticação do Spotify

# Tente importar pyttsx3 para fala offline (opcional)
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# Tente importar bibliotecas para controle de volume (Windows)
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

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
# USE SEUS DADOS AQUI!
os.environ['SPOTIPY_CLIENT_ID'] = 'd2029dbe36b7479fbb1b4768e3d5246e'
os.environ['SPOTIPY_CLIENT_SECRET'] = '76034efe75da40c78b81fdaed161e9ff'
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://127.0.0.1:8888/callback' # Use um dos seus Redirect URIs registrados

# Definindo os escopos necessários para reprodução
# user-read-playback-state: para ler o estado de reprodução
# user-modify-playback-state: para controlar a reprodução (play, pause, skip)
# user-read-currently-playing: para ver a música atual
SCOPE = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing"

sp = None # Variável global para a instância do Spotipy
def authenticate_spotify():
    global sp
    try:
        auth_manager = SpotifyOAuth(scope=SCOPE, cache_path=".spotify_token_cache")
        # O .spotify_token_cache é um arquivo onde o spotipy guarda o token
        # para não precisar autenticar novamente toda hora.
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

def speak(text):
    print("[SPEAK ONLINE]", text)
    try:
        tts = gTTS(text=text, lang='pt')
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
        if "brazil" in voice.name.lower():
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
        # Busca por tracks
        results = sp.search(q=music_name, type='track', limit=1)
        if not results['tracks']['items']:
            return speak(f"Não encontrei a música {music_name} no Spotify.")

        track_uri = results['tracks']['items'][0]['uri']
        track_name = results['tracks']['items'][0]['name']
        artist_name = results['tracks']['items'][0]['artists'][0]['name']

        # Tenta encontrar um dispositivo ativo
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
            # Se não houver dispositivo ativo, tenta transferir para o primeiro encontrado
            if devices['devices']:
                speak("Nenhum dispositivo Spotify ativo. Tentando iniciar no primeiro dispositivo encontrado.")
                first_device_id = devices['devices'][0]['id']
                sp.transfer_playback(device_id=first_device_id, force_play=True)
                # Dá um pequeno tempo e tenta iniciar a música novamente no dispositivo transferido
                time.sleep(1) 
                sp.start_playback(device_id=first_device_id, uris=[track_uri])
                speak(f"Tocando {track_name} de {artist_name} no Spotify.")
            else:
                speak("Não encontrei nenhum dispositivo Spotify para tocar a música. Por favor, abra o Spotify em algum lugar.")
                # Fallback: abrir no navegador de pesquisa como antes
                webbrowser.open(f"https://open.spotify.com/search/{music_name.replace(' ', '%20')}")


    except spotipy.exceptions.SpotifyException as se:
        print(f"Erro do Spotify API: {se}")
        if "Authentication failed" in str(se):
            speak("Sua sessão do Spotify expirou ou está inválida. Por favor, autentique novamente.")
            # Remove o cache para forçar nova autenticação na próxima vez
            if os.path.exists(".spotify_token_cache"):
                os.remove(".spotify_token_cache")
            sp = None
        else:
            speak("Ocorreu um erro com o Spotify. Verifique se o Spotify está aberto.")
    except Exception as e:
        print(f"Erro ao tocar música no Spotify: {e}")
        speak("Desculpe, ocorreu um erro inesperado ao tentar tocar a música no Spotify.")


# --- LOOP PRINCIPAL CONSOLIDADO ---
speak("Assistente pronta. Diga 'Ok Jarvis' para ativar.")

# Autentica o Spotify ao iniciar o assistente
authenticate_spotify()

try:
    while True:
        print("\nAguardando wake word...")
        wake = listen(timeout=10, phrase_time_limit=4)
        if any(w in wake for w in ["ok Jarvis", "ok Jarvis", "Jarvis", "Jarvis"]):
            speak("Sim?")
            cmd = listen(timeout=6, phrase_time_limit=7)
            print("Comando:", cmd)
            if not cmd:
                speak("Não ouvi nenhum comando.")
                continue

            # --- Bloco de Comandos ---
            if any(w in cmd for w in ["cadastrar evento", "novo evento"]):
                speak("Ok, qual evento devo cadastrar?")
                ev = listen(timeout=8, phrase_time_limit=10)
                if ev: add_event(ev)
                else: speak("Não consegui ouvir o evento.")

            elif any(w in cmd for w in ["ler agenda", "mostrar agenda"]):
                read_agenda()

            elif "limpar agenda" in cmd:
                clear_agenda()

            elif any(w in cmd for w in ["que horas", "horas são"]):
                speak(f"Agora são {datetime.datetime.now().strftime('%H:%M')}.")

            elif any(w in cmd for w in ["que dia", "data de hoje"]):
                speak(f"Hoje é {datetime.datetime.now().strftime('%d de %B de %Y')}.")

            elif any(w in cmd for w in ["previsão", "clima", "tempo"]):
                speak("Para qual cidade?")
                city = listen(timeout=5, phrase_time_limit=5)
                if city: speak(get_weather(city))
                else: speak("Não entendi o nome da cidade.")
            
            elif any(w in cmd for w in ["cotação", "valor", "preço", "dólar", "euro", "bitcoin"]):
                found_currency = next((data for name, data in CURRENCY_MAP.items() if name in cmd), None)
                if found_currency:
                    speak(get_currency_rate(found_currency['code'], found_currency['name']))
                else: speak("Não reconheci essa moeda. Tente dólar, euro ou bitcoin.")

            elif any(w in cmd for w in ["print", "capturar tela"]):
                speak("Ok, tirando um print.")
                speak(take_screenshot())

            elif any(w in cmd for w in ["ajustar volume", "colocar volume"]):
                match = re.search(r'\d+', cmd)
                if match: speak(set_volume(int(match.group(0))))
                else: speak("Não entendi o nível. Diga um número de 0 a 100.")

            elif any(w in cmd for w in ["aumentar volume", "mais alto"]):
                speak(change_volume(0.10))

            elif any(w in cmd for w in ["abaixar volume", "diminuir volume"]):
                speak(change_volume(-0.10))

            elif any(w in cmd for w in ["equação", "resolver"]):
                resolver_equacao(cmd)
            
            # --- NOVO COMANDO PARA O SPOTIFY API ---
            elif "tocar música" in cmd and "spotify" in cmd:
                match = re.search(r"tocar música\s+(.*?)(?:\s+no spotify)?$", cmd)
                if match:
                    music_name = match.group(1).strip()
                    if music_name:
                        play_spotify_music_api(music_name) # Chama a nova função da API
                    else:
                        speak("Qual música você gostaria de tocar?")
                else:
                    speak("Qual música você gostaria de tocar?")


            elif any(w in cmd for w in ["sair", "encerrar", "desligar"]):
                speak("Encerrando assistente. Até mais.")
                break

            else:
                try:
                    speak(f"O resultado é {safe_eval(cmd)}")
                except (ValueError, SyntaxError):
                    speak("Comando não reconhecido. Tente novamente.")

except KeyboardInterrupt:
    speak("Encerrando por interrupção.")
except Exception as e:
    print("Erro principal:", e)
    speak("Ocorreu um erro, veja o console.")