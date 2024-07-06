import os
import math
import datetime
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import pytz

# Инициализация бота, хранилища и диспетчера
bot = Bot(token='7174669599:AAEB13LM4dW79Vsac4Ru3gpUwhXXXgDAWbw')
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Словарь для отображения погодных условий
code_to_smile = {
    "Clear": "Ясно \U00002600",
    "Clouds": "Облачно \U00002601",
    "Rain": "Дождь \U00002614",
    "Drizzle": "Дождь \U00002614",
    "Thunderstorm": "Гроза \U000026A1",
    "Snow": "Снег \U0001F328",
    "Mist": "Туман \U0001F32B"
}

# Словарь для советов по погоде
weather_advices = {
    "Clear": "Сегодня ясная погода, не забудьте надеть солнечные очки!",
    "Clouds": "Облачно с прояснениями. Лучше возьмите с собой зонтик, вдруг дождь начнется.",
    "Rain": "Сегодня дождливо. Не забудьте взять зонтик и непромокаемую обувь.",
    "Thunderstorm": "Гроза в районе? Лучше оставайтесь в помещении и следите за новостями.",
    "Snow": "Снег идет? Не забудьте одеть теплую куртку и обувь.",
    "Mist": "Туманность. Будьте осторожны на дороге, включите фары."
}

# Inline-кнопки для меню
button_weather_now = InlineKeyboardButton('Погода в данный момент', callback_data='weather_now')
button_weather_5_days = InlineKeyboardButton('Прогноз на 5 дней', callback_data='weather_5_days')
keyboard_menu = InlineKeyboardMarkup().add(button_weather_now, button_weather_5_days)

# Класс состояний для FSM (машины состояний)
class WeatherState(StatesGroup):
    waiting_for_city = State()

# Обработчик команды /start
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.reply("Выберите опцию:", reply_markup=keyboard_menu)

# Обработчик inline-кнопок
@dp.callback_query_handler(lambda c: c.data in ['weather_now', 'weather_5_days'])
async def inline_menu_handler(callback_query: types.CallbackQuery, state: FSMContext):
    forecast_type = callback_query.data
    await callback_query.message.reply("Напишите название города.")
    await state.set_state(WeatherState.waiting_for_city)
    await state.update_data(forecast_type=forecast_type)
    await callback_query.answer()

# Функция для получения временной зоны города с использованием TimeZoneDB API
def get_timezone(lat, lon):
    try:
        response = requests.get(
            f"http://api.timezonedb.com/v2.1/get-time-zone",
            params={
                'key': 'BLVTMUWSG2DE',
                'format': 'json',
                'by': 'position',
                'lat': lat,
                'lng': lon
            }
        )
        
        data = response.json()
        if data['status'] == 'OK':
            return data['zoneName']
        else:
            print(f"Error in get_timezone: {data}")
            return None
    except Exception as e:
        print(f"Exception in get_timezone: {e}")
        return None

# Обработчик сообщений для получения погоды
@dp.message_handler(state=WeatherState.waiting_for_city)
async def get_weather(message: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        forecast_type = user_data.get("forecast_type")
        city_name = message.text

        # Получение данных о погоде через API OpenWeatherMap
        city_response = requests.get(
            f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid=b01e1d140746da92c8ecec5c5258b712"
        )
        city_data = city_response.json()

        # Проверка наличия города в базе данных
        if city_data["cod"] != 200:
            await message.reply("Город не найден, попробуйте еще раз", reply_markup=keyboard_menu)
            return

        lat = city_data["coord"]["lat"]
        lon = city_data["coord"]["lon"]
        timezone_name = get_timezone(lat, lon)

        # Проверка наличия временной зоны
        if not timezone_name:
            await message.reply("Не удалось определить временную зону города.", reply_markup=keyboard_menu)
            return

        timezone = pytz.timezone(timezone_name)

        # Прогноз на пять дней
        if forecast_type == "weather_5_days":
            forecast_response = requests.get(
                f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&appid=b01e1d140746da92c8ecec5c5258b712"
            )
            forecast_data = forecast_response.json()

            if forecast_data["cod"] != "200":
                await message.reply("Не удалось получить прогноз погоды, попробуйте еще раз", reply_markup=keyboard_menu)
                return

            # Создание графиков для каждого дня прогноза
            days_data = {}
            for entry in forecast_data["list"]:
                dt = datetime.datetime.fromtimestamp(entry["dt"], tz=pytz.utc).astimezone(timezone)
                date_str = dt.strftime('%Y-%m-%d')
                if date_str not in days_data:
                    days_data[date_str] = {'times': [], 'temps': []}
                days_data[date_str]['times'].append(dt)
                days_data[date_str]['temps'].append(entry["main"]["temp"])
            # Построение графиков
            for date_str, data in days_data.items():
                plt.figure(figsize=(10, 5))
                plt.plot(data['times'], data['temps'], marker='o', linestyle='-', color='b')
                plt.title(f'Прогноз температуры на {date_str} для {city_name}')
                plt.xlabel('Время')
                plt.ylabel('Температура (°C)')
                plt.grid(True)
                plt.xticks(rotation=45)
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                plt.tight_layout()

                graph_path = f'weather_forecast_{city_name}_{date_str}.png'
                plt.savefig(graph_path)
                plt.close()

                with open(graph_path, 'rb') as photo:
                    await message.reply_photo(photo, reply_markup=keyboard_menu)
        else:
            # Получение данных о текущей погоде
            weather_response = requests.get(
                f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&lang=ru&units=metric&appid=b01e1d140746da92c8ecec5c5258b712"
            )
            weather_data = weather_response.json()

            # Проверка успешности получения данных о погоде
            if weather_data["cod"] == "404":
                await message.reply("Город не найден, попробуйте еще раз", reply_markup=keyboard_menu)
                return
            
            # Отправка сообщения о текущей погоде с советом
            city = weather_data["name"]
            cur_temp = weather_data["main"]["temp"]
            humidity = weather_data["main"]["humidity"]
            pressure = weather_data["main"]["pressure"]
            wind = weather_data["wind"]["speed"]

            sunrise_timestamp = datetime.datetime.fromtimestamp(weather_data["sys"]["sunrise"], tz=timezone)
            sunset_timestamp = datetime.datetime.fromtimestamp(weather_data["sys"]["sunset"], tz=timezone)

            length_of_the_day = sunset_timestamp - sunrise_timestamp
            weather_description = weather_data["weather"][0]["main"]
            wd = code_to_smile.get(weather_description, "Посмотри в окно, я не понимаю, что там за погода...")
            advice = weather_advices.get(weather_description, "Сегодня хорошая погода. Хорошего дня!")
            # Отправка сообщения о текущей погоде с советом
            await message.reply(
                f"{datetime.datetime.now(timezone).strftime('%Y-%m-%d %H:%M')}\n"
                f"Погода в городе: {city}\nТемпература: {cur_temp}°C {wd}\n"
                f"Влажность: {humidity}%\nДавление: {math.ceil(pressure / 1.333)} мм.рт.ст\n"
                f"Ветер: {wind} м/с\n"
                f"Восход солнца: {sunrise_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Закат солнца: {sunset_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Продолжительность дня: {length_of_the_day}\n"
                f"Совет: {advice}\n"
                f"Хорошего дня!",
                reply_markup=keyboard_menu
            )

    except Exception as e:
        await message.reply("Произошла ошибка при получении данных о погоде. Пожалуйста, попробуйте снова позже.", reply_markup=keyboard_menu)
        print(f"Exception in get_weather: {e}")
    finally:
        await state.finish()

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен.")
    executor.start_polling(dp, skip_updates=True)


