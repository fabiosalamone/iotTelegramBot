from sys import exec_prefix
from time import sleep
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import paho.mqtt.client as mqtt
import emoji
import requests
import telegram
from datetime import datetime
import pytz
import os

# Il token del bot Telegram è stato impostato come variabile d'ambiente su Heroku per motivi di sicurezza
TOKEN = os.environ["TOKEN"]
topicList = "http://serveriotsaldep.herokuapp.com/topiclist"
botTelegram = telegram.Bot(token = TOKEN)

messaggio = "" #contenuto del payload
def on_connect(client, userdata, flags, rc):  # The callback for when the client connects to the broker
    print("Connected with result code {0}".format(str(rc)))  # Print result of connection attempt

def on_message(client, userdata, msg):  # The callback for when a PUBLISH message is received from the server.
    global messaggio
    print("Message received-> " + msg.topic + " " + msg.payload.decode("utf-8"))  # Print a received msg
    messaggio = msg.payload.decode("utf-8")
    if msg.topic == topicDict["giardinomovement"]:
        for key,value in dizionarioUtenti.items():
            timezone = pytz.timezone('Europe/Rome') 
            now = datetime.now(timezone)
            current_time = now.strftime("%H:%M:%S")
            botTelegram.sendMessage(chat_id = key, text = "Movimento rilevato alle "+current_time)

client = mqtt.Client("IOTSalDepTelegram")  # Create instance of client 
client.on_connect = on_connect  # Define callback function for successful connection
client.on_message = on_message  # Define callback function for receipt of a message
client.username_pw_set("adepalma", "iot874351")
client.connect('149.132.178.180', 1883, 17300)
client.loop_start()  # Start networking daemon


deviceDict =  {}
topicDict = {}
count = 0
keyboard = []

buttonToStart = InlineKeyboardButton(text="Indietro", callback_data="buttonToStart")
keyboardToStart = InlineKeyboardMarkup().add(buttonToStart)

dizionarioUtenti = {} # associazione chat id - lastMessage id

bot = Bot(TOKEN)
dp = Dispatcher(bot)

# Alla ricezione del comando /start viene mostrato un messaggio di benvenuto con le stanze trovate
@dp.message_handler(commands=["start"])
async def welcome(message: types.Message):
    r = requests.get(topicList)
    deviceDict = json.loads(r.text).get("data")
    global topicDict
    topicDict = {}
    count = 0
    keyboard = []
    for device in deviceDict:
        room = deviceDict[count][1]
        parsed = json.loads(deviceDict[count][0])
        for key, value in parsed.items():
            topicDict[room+key] = value #salvo le coppie stanza topic in un dict
        keyboard.append([
            InlineKeyboardButton(
                text=room.capitalize(), 
                callback_data=room)
                ])
        if room+"movement" in topicDict:
            client.subscribe(topicDict[room+"movement"], qos=2)
        count = count+1
    global keyboard_Iniziale
    keyboard.append([
        InlineKeyboardButton(
            text=emoji.emojize(":magnifying_glass_tilted_left:")+" Aggiorna", 
            callback_data="buttonAggiorna")
        ])
    keyboard_Iniziale = InlineKeyboardMarkup(inline_keyboard = keyboard)

    lastMessage = await message.answer("Ciao, benvenuto in Smart Home Monitor"+"\n"+"Scegli un ambiente: ", reply_markup = keyboard_Iniziale)
    dizionarioUtenti[message.chat.id] = lastMessage.message_id
    print(dizionarioUtenti)

# In base al bottone premuto (contenuto di call.data) viene eseguita un'azione diversa
@dp.callback_query_handler(lambda callback_query: True)
async def show_value(call: types.CallbackQuery):
    print(call.data)
    if call.data == "buttonAggiorna":
        await bot.delete_message(call.message.chat.id, dizionarioUtenti[call.message.chat.id])
        r = requests.get(topicList)
        deviceDict = json.loads(r.text).get("data")
        global topicDict
        topicDict = {}
        count = 0
        keyboard = []
        for device in deviceDict:
            room = deviceDict[count][1]
            parsed = json.loads(deviceDict[count][0])
            for key, value in parsed.items():
                topicDict[room+key] = value #salvo le coppie stanza topic in un dict
            keyboard.append([
                InlineKeyboardButton(
                    text=room.capitalize(), 
                    callback_data=room)
                    ])
            if room+"movement" in topicDict:
                client.subscribe(topicDict[room+"movement"], qos=2)
            count = count+1
        global keyboard_Iniziale
        keyboard.append([
            InlineKeyboardButton(
                text=emoji.emojize(":magnifying_glass_tilted_left:")+" Aggiorna",
                callback_data="buttonAggiorna")
            ])
        keyboard_Iniziale = InlineKeyboardMarkup(inline_keyboard = keyboard)

        lastMessage = await call.message.answer("Ciao, benvenuto in Smart Home Monitor"+"\n"+"Scegli un ambiente: ", reply_markup = keyboard_Iniziale)
        dizionarioUtenti[call.message.chat.id] = lastMessage.message_id

    elif call.data == "buttonToStart":
        await bot.delete_message(call.message.chat.id, dizionarioUtenti[call.message.chat.id])
        lastMessage = await call.message.answer("Ciao, benvenuto in Smart Home Monitor"+"\n"+"Scegli un ambiente: ", reply_markup = keyboard_Iniziale)
        dizionarioUtenti[call.message.chat.id] = lastMessage.message_id
    elif "accendiAllarme" in call.data:
        await bot.delete_message(call.message.chat.id, dizionarioUtenti[call.message.chat.id])
        mac = call.data.split(" ")[1]
        client.publish(topic = "IOTSalDep/"+mac+"/status", payload="on", qos = 2, retain = True)
        lastMessage = await call.message.answer("Allarme attivato", reply_markup = keyboard_Iniziale)
        dizionarioUtenti[call.message.chat.id] = lastMessage.message_id
    elif "spegniAllarme" in call.data:
        await bot.delete_message(call.message.chat.id, dizionarioUtenti[call.message.chat.id])
        mac = call.data.split(" ")[1]
        client.publish(topic = "IOTSalDep/"+mac+"/status", payload="off", qos = 2, retain = True)
        lastMessage = await call.message.answer("Allarme disattivato", reply_markup = keyboard_Iniziale)
        dizionarioUtenti[call.message.chat.id] = lastMessage.message_id
    else:
        await bot.delete_message(call.message.chat.id, dizionarioUtenti[call.message.chat.id])
        rilevazioni = "\n"
        keyboard = []
        #Leggere i dati dalla subscribe
        if call.data+"temp" in topicDict:
            client.subscribe(topicDict[call.data+"temp"], qos=2)
            sleep(0.2)
            temp = emoji.emojize(":thermometer:")+" Temperatura: "+messaggio+"°C"+"\n\n" 
            rilevazioni = rilevazioni + temp
        if call.data+"hum" in topicDict:
            client.subscribe(topicDict[call.data+"hum"], qos=2)
            sleep(0.2)
            hum = emoji.emojize(":droplet:")+" Umidità: "+messaggio+"%"+"\n\n"
            rilevazioni = rilevazioni + hum
        if call.data+"light" in topicDict:
            client.subscribe(topicDict[call.data+"light"], qos=2)
            sleep(0.2)
            light = emoji.emojize(":light_bulb:")+" Luce: "+messaggio+"\n\n"
            rilevazioni = rilevazioni + light       
        if call.data+"status" in topicDict:
            client.subscribe(topicDict[call.data+"status"], qos=2)
            mac = topicDict[call.data+"mac"]
            sleep(0.2)
            status = emoji.emojize(":warning:")+" Stato allarme: "+messaggio+"\n\n"
            rilevazioni = rilevazioni + status
            if messaggio == "off":
                azione = "Accendi"
                callback_allarme = "accendiAllarme "+mac
            else:
                azione = "Spegni"
                callback_allarme = "spegniAllarme "+mac
            keyboard.append([
            InlineKeyboardButton(
                text=azione+" allarme",
                callback_data=callback_allarme)
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                text="Indietro",
                callback_data="buttonToStart")
            ])
        keyboardAction = InlineKeyboardMarkup(inline_keyboard = keyboard)
        lastMessage = await call.message.answer("Rilevazioni in "+call.data+"\n"+rilevazioni, reply_markup = keyboardAction)
        dizionarioUtenti[call.message.chat.id] = lastMessage.message_id    
    await call.answer() 

executor.start_polling(dp)