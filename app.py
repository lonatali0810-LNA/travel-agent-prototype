import streamlit as st
import pandas as pd
import random
import re
from datetime import datetime, timedelta
import requests
from io import StringIO

# 1. Настройка страницы
st.set_page_config(page_title="AI Тревел-Агент", page_icon="✈️", layout="wide")

# 2. Загрузка данных
# @st.cache_data  <-- кэш временно отключен для отладки
def load_data():
    # Ссылки на "сырые" файлы (формат main)
    url_hotels = 'https://raw.githubusercontent.com/lonatali0810-LNA/travel-agent-prototype/refs/heads/main/hotels_dictionary.csv'
    url_flights = 'https://raw.githubusercontent.com/lonatali0810-LNA/travel-agent-prototype/refs/heads/main/flights_mock.csv'
    url_transfers = 'https://raw.githubusercontent.com/lonatali0810-LNA/travel-agent-prototype/refs/heads/main/transfers_mock.csv'
    
    # Добавляем заголовок User-Agent, чтобы GitHub не блокировал запрос
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Скачиваем данные как текст и превращаем в DataFrame
    response_hotels = requests.get(url_hotels, headers=headers)
    response_hotels.raise_for_status() # Если будет ошибка, она покажет точный код
    hotels = pd.read_csv(StringIO(response_hotels.text), encoding='utf-8')
    
    response_flights = requests.get(url_flights, headers=headers)
    response_flights.raise_for_status()
    flights = pd.read_csv(StringIO(response_flights.text), encoding='utf-8')
    
    response_transfers = requests.get(url_transfers, headers=headers)
    response_transfers.raise_for_status()
    transfers = pd.read_csv(StringIO(response_transfers.text), encoding='utf-8')
    
    return hotels, flights, transfers


try:
    df_hotels, df_flights, df_transfers = load_data()
except Exception as e:
    # Ловим любую ошибку, чтобы видеть, что именно пошло не так
    st.error(f"❌ Ошибка при загрузке данных: {e}")
    st.stop()

# Вспомогательная функция для звезд
def format_stars(stars):
    if pd.isna(stars) or stars == -1 or stars == -1.0:
        return "без звезд"
    return f"{int(stars)}*"

# 3. Инициализация сессии (память агента)
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'selected_package' not in st.session_state:
    st.session_state.selected_package = None

# 4. Интерфейс чата
st.title("✈️ AI Тревел-Агент")
st.caption("Опишите, куда хотите поехать, и я соберу для вас готовый тур.")

# Выводим историю сообщений
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 5. Ввод пользователя
if prompt := st.chat_input("Например: Хочу в Сочи, бюджет до 30000 рублей"):
    # Добавляем сообщение пользователя
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- ЛОГИКА АГЕНТА ---
    with st.chat_message("assistant"):
        text = prompt.lower()
        
        # Ищем город в тексте
        known_cities = df_hotels['city'].dropna().unique()
        found_city = next((c for c in known_cities if c.lower() in text), None)
        
        if not found_city:
            if any(word in text for word in ['море', 'пляж', 'побережье', 'покупаться']):
                top_cities = df_hotels['city'].value_counts().head(5).index.tolist()
                response = f"Понял, вы хотите к морю! У нас есть отличные варианты в таких городах: {', '.join(top_cities)}.\nВ какой из этих городов вам подобрать отели?"
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                response = "Я пока не понял, куда именно вы хотите поехать. Уточните город? (Например: Сочи, Сухум, Гагра)"
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
        else:
            # Ищем отели (фильтр > 1500 руб)
            city_hotels = df_hotels[
                (df_hotels['city'].str.lower() == found_city.lower()) & 
                (df_hotels['price_rub'] > 1500) 
            ].sort_values('price_rub').head(3)
            
            if city_hotels.empty:
                response = f"К сожалению, в {found_city} пока нет подходящих отелей в базе."
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                st.markdown(f"Отлично! Вот варианты для поездки в **{found_city}**:")
                
                packages = []
                city_flights = df_flights[df_flights['to_city'].str.lower() == found_city.lower()]
                flight = city_flights.sample(1).iloc[0] if not city_flights.empty else None
                
                city_transfers = df_transfers[df_transfers['city'].str.lower() == found_city.lower()]
                transfer = city_transfers.sample(1).iloc[0] if not city_transfers.empty else None
                
                # Выводим карточки
                for idx, hotel in city_hotels.iterrows():
                    total_price = hotel['price_rub'] + (flight['price'] if flight is not None else 0) + (transfer['price'] if transfer is not None else 0)
                    
                    pkg = {
                        'hotel': hotel,
                        'flight': flight,
                        'transfer': transfer,
                        'total_price': total_price
                    }
                    packages.append(pkg)
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            stars_text = format_stars(hotel['stars'])
                            st.subheader(f"{hotel['name']} ({stars_text})")
                            st.write(f"**Номер:** {hotel['room_name']}")
                        with col2:
                            st.metric("Итого за тур", f"{int(total_price)} ₽")
                            if st.button(f"Забронировать", key=f"book_{idx}"):
                                st.session_state.selected_package = pkg
                                st.rerun() 

                st.session_state.messages.append({"role": "assistant", "content": f"Найдено {len(packages)} вариантов в {found_city}. Выберите подходящий!"})

# 6. УМНАЯ ФОРМА БРОНИРОВАНИЯ (в боковой панели)
if st.session_state.selected_package is not None:
    pkg = st.session_state.selected_package
    
    with st.sidebar:
        st.header("📝 Оформление брони")
        st.write(f"Вы выбрали: **{pkg['hotel']['name']}**")
        
        with st.form("booking_form"):
            name = st.text_input("Ваше имя")
            phone = st.text_input("Ваш телефон (например, +79991234567)")
            email = st.text_input("Ваш email")
            guests = st.number_input("Количество гостей", min_value=1, max_value=10, value=2)
            start_date = st.date_input("Дата заезда", datetime.now() + timedelta(days=1))
            comments = st.text_area("Пожелания")
            
            submitted = st.form_submit_button("Подтвердить и оплатить")
            
            if submitted:
                # Очищаем телефон от всех символов, кроме цифр
                clean_phone = re.sub(r'\D', '', phone)
                
                if not name or len(clean_phone) < 10:
                    st.error("Заполните имя и введите корректный телефон (минимум 10 цифр)!")
                else:
                    # Генерируем умный ID клиента на основе последних 4 цифр
                    client_id = f"CLIENT-{clean_phone[-4:]}"
                    
                    # --- ЗАПИСЬ В BOOKINGS.CSV ---
                    new_booking = {
                        'id_tour': f"TOUR-{random.randint(1000, 9999)}",
                        'id_client': client_id,
                        'reservation_number': f"RES-{random.randint(100000, 999999)}",
                        'person_count': guests,
                        'rooms_number': 1,
                        'guest_number': phone,
                        'guest_email': email,
                        'start_tour_date': str(start_date),
                        'end_tour_date': str(start_date + timedelta(days=3)),
                        'country': '', 
                        'city': pkg['hotel']['city'],
                        'activity': 'Отдых',
                        'hotel_type': pkg['hotel']['type'],
                        'hotel_name': pkg['hotel']['name'],
                        'room_type': pkg['hotel']['room_name'],
                        'booking_status': 'Ожидает оплаты',
                        'hotel_number': pkg['hotel']['hotel_number'],
                        'hotel_email': pkg['hotel']['hotel_email'],
                        'payment_status': 'Unpaid',
                        'currency': 'RUB',
                        'comments': comments,
                        'room_code': pkg['hotel']['room_code'],
                        'flight_id': pkg['flight']['flight_id'] if pkg['flight'] is not None else '',
                        'transfer_id': pkg['transfer']['transfer_id'] if pkg['transfer'] is not None else ''
                    }
                   
                    try:
                        # Временно отключаем запись в файл, так как облако только для чтения
                        # Просто имитируем успешное сохранение для демонстрации
                        print("Новая бронь (демо):", new_booking) 
                        
                        st.success(f"✅ Бронь {new_booking['reservation_number']} успешно создана! (Демо-режим)")
                        st.info(f"Ваш ID клиента: {client_id} (сохранен для будущих покупок)")
                        st.balloons()
                        
                        # Сбрасываем выбор и историю чата
                        st.session_state.selected_package = None
                        st.session_state.messages = []
                    except Exception as e:
                        st.error(f"Ошибка при сохранении: {e}")
