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
import webbrowser 
import threading # Para controlar a reprodução de áudio em uma thread separada

# --- BIBLIOTECAS DE TERCEIROS (FUNCIONALIDADES ADICIONAIS) ---
import requests  # Para Clima e Moedas
import spotipy 
from spotipy.oauth2 import SpotifyOAuth 

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
    from pycaw.pycaw import AudioUtilities, IAudioEndpointEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
    print("Biblioteca 'pycaw' não encontrada. Controle de volume não estará disponível.")


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

sp = None 
def authenticate_spotify():
    global sp
    try:
        auth_manager = SpotifyOAuth(scope=SCOPE, cache_path=".spotify_token_cache")
        sp = spotipy.Spotify(auth_manager=auth_manager)
        speak("Conectado ao Spotify.")
    except Exception as e:
        print(f"Erro ao autenticar com Spotify: {e}")
        speak("Não consegui conectar ao Spotify. Verifique suas credenciais e permissões.")
        sp = None 

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

# --- Variáveis para controle de áudio ---
stop_audio_flag = threading.Event()
audio_thread = None

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
        forecast = f"A temperatura em {data['name']} é de {data['main']['temp']:.0f} graus Celsius, com tempo {data['weather'][0]['description']}."
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
        if sp is None: 
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

# --- FUNÇÃO PARA ABRIR VÍDEOS DO YOUTUBE ---
def open_youtube_video(query=None): 
    if query:
        search_query = query.replace(' ', '+')
        youtube_url = f"https://www.youtube.com/results?search_query={search_query}"
        speak(f"Abrindo YouTube com a pesquisa por {query}.")
    else:
        youtube_url = "https://www.youtube.com"
        speak("Abrindo YouTube.")
    
    try:
        webbrowser.open(youtube_url)
    except Exception as e:
        print(f"Erro ao abrir o navegador para o YouTube: {e}")
        speak("Desculpe, não consegui abrir o YouTube no seu navegador.")

# --- FUNÇÃO PARA ABRIR O SPOTIFY DIRETO ---
def open_spotify_app():
    speak("Abrindo Spotify.")
    try:
        webbrowser.open("spotify:") 
    except Exception as e:
        print(f"Erro ao tentar abrir o aplicativo Spotify: {e}. Tentando abrir no navegador.")
        webbrowser.open("https://open.spotify.com") 
        speak("Não consegui abrir o aplicativo Spotify, abrindo no navegador.")


# --- FUNÇÃO PARA ABRIR O PORTAL DA FACULDADE ---
def open_college_portal():
    college_url = "https://aluno.uninove.br/seu/CENTRAL/aluno/"
    speak("Abrindo o portal da faculdade.")
    try:
        webbrowser.open(college_url)
    except Exception as e:
        print(f"Erro ao abrir o navegador para o portal da faculdade: {e}")
        speak("Desculpe, não consegui abrir o portal da faculdade no seu navegador.")

# --- FUNÇÃO PARA ABRIR O WHATSAPP ---
def open_whatsapp():
    speak("Abrindo WhatsApp.")
    try:
        webbrowser.open("whatsapp://")
        time.sleep(1) 
    except Exception as e:
        print(f"Erro ao tentar abrir o aplicativo WhatsApp: {e}. Tentando abrir no navegador.")
        webbrowser.open("https://web.whatsapp.com/")
        speak("Não consegui abrir o aplicativo WhatsApp, abrindo o WhatsApp Web no navegador.")

# --- FUNÇÃO PARA ABRIR O XBOX APP OU WEB ---
def open_xbox_app():
    speak("Abrindo Xbox.")
    try:
        webbrowser.open("ms-xbox-gamepass://") 
        time.sleep(1)
    except Exception as e:
        print(f"Erro ao tentar abrir o aplicativo Xbox: {e}. Tentando abrir o Xbox Cloud Gaming no navegador.")
        webbrowser.open("https://www.xbox.com/play") 
        speak("Não consegui abrir o aplicativo Xbox, abrindo o Xbox Cloud Gaming no navegador.")

def _play_audio_loop(audio_file, stop_event):
    while not stop_event.is_set():
        try:
            playsound(audio_file)
            if stop_event.is_set():
                break
        except Exception as e:
            print(f"Erro ao tocar o arquivo {audio_file}: {e}")
            break

def play_bad_time_audio():
    global audio_thread, stop_audio_flag
    audio_file = "sans.mp3"
    if os.path.exists(audio_file):
        speak(f"Tocando {audio_file}. Você está tendo um tempo ruim.")
        stop_audio_flag.clear() # Garante que o flag de parada esteja limpo
        audio_thread = threading.Thread(target=_play_audio_loop, args=(audio_file, stop_audio_flag))
        audio_thread.start()
    else:
        speak(f"Desculpe, não encontrei o arquivo de áudio {audio_file}.")

def stop_playing_audio():
    global audio_thread, stop_audio_flag
    if audio_thread and audio_thread.is_alive():
        stop_audio_flag.set()
        audio_thread.join(timeout=1) # Espera a thread terminar por um curto período
        speak("Áudio parado.")
    else:
        speak("Nenhum áudio de bad time está tocando.")


def main_loop():
    speak("Olá, como posso ajudar?")
    while True:
        command = listen()
        if not command:
            continue

        print(f"Comando recebido: {command}")

        if "horas" in command:
            speak(f"Agora são {datetime.datetime.now().strftime('%H:%M')}")
        elif "que dia é hoje" in command:
            speak(f"Hoje é {datetime.datetime.now().strftime('%d de %B de %Y')}")
        elif "adicionar evento" in command:
            speak("Qual evento você gostaria de adicionar?")
            event_text = listen()
            if event_text:
                add_event(event_text)
            else:
                speak("Não entendi o evento.")
        elif "ler agenda" in command:
            read_agenda()
        elif "limpar agenda" in command:
            speak("Tem certeza que deseja limpar a agenda?")
            confirm = listen()
            if "sim" in confirm or "claro" in confirm:
                clear_agenda()
            else:
                speak("Limpeza da agenda cancelada.")
        elif "calcular" in command:
            speak("Qual cálculo você quer fazer?")
            calculation = listen(timeout=10, phrase_time_limit=8)
            if calculation:
                try:
                    result = safe_eval(calculation)
                    speak(f"O resultado é {result:.2f}")
                except (ValueError, TypeError, SyntaxError) as e:
                    speak(f"Não consegui resolver. Erro: {e}")
            else:
                speak("Não entendi o cálculo.")
        elif "resolver equação" in command:
            speak("É uma equação de primeiro ou segundo grau?")
            eq_type = listen()
            resolver_equacao(eq_type)
        elif "qual o clima" in command or "previsão do tempo" in command:
            speak("De qual cidade você quer saber o clima?")
            city = listen()
            if city:
                weather_info = get_weather(city)
                speak(weather_info)
            else:
                speak("Não entendi a cidade.")
        elif "cotação do" in command:
            for key, val in CURRENCY_MAP.items():
                if key in command:
                    speak(get_currency_rate(val['code'], val['name']))
                    break
            else:
                speak("Não entendi qual moeda.")
        elif "aumentar volume" in command:
            speak(change_volume(0.1))
        elif "diminuir volume" in command:
            speak(change_volume(-0.1))
        elif "definir volume para" in command:
            try:
                parts = command.split("definir volume para")
                if len(parts) > 1:
                    level_str = re.search(r'\d+', parts[1])
                    if level_str:
                        level_percent = int(level_str.group())
                        speak(set_volume(level_percent))
                    else:
                        speak("Por favor, diga o nível do volume em porcentagem, como 'definir volume para 50 por cento'.")
                else:
                    speak("Por favor, diga o nível do volume em porcentagem.")
            except ValueError:
                speak("Não entendi o nível do volume. Por favor, diga um número.")
        elif "tocar música" in command or "tocar canção" in command:
            speak("Que música você gostaria de tocar?")
            music_name = listen()
            if music_name:
                play_spotify_music_api(music_name)
            else:
                speak("Não entendi o nome da música.")
        elif "abrir youtube" in command:
            if "pesquisar por" in command:
                query = command.split("pesquisar por", 1)[1].strip()
                open_youtube_video(query)
            else:
                open_youtube_video()
        elif "abrir spotify" in command:
            open_spotify_app()
        elif "abrir portal da faculdade" in command:
            open_college_portal()
        elif "abrir conversas" in command:
            open_whatsapp()
        elif "jogar" in command:
            open_xbox_app()
        elif "bad time" in command: 
            play_bad_time_audio() 
        elif "parar" in command and "audio" in command or "parar de tocar" in command: # Novo comando para parar o áudio
            stop_playing_audio()
        elif "encerrar" in command or "desligar" in command:
            speak("Até mais!")
            break
        else:
            speak("Não entendi o comando.")

if __name__ == "__main__":
    authenticate_spotify()
    main_loop()
