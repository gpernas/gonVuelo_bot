import os
import asyncio
import logging
import re
from amadeus import Client, ResponseError

logger = logging.getLogger(__name__)

AIRLINE_NAMES = {
    'FR': 'Ryanair', 'VY': 'Vueling', 'U2': 'easyJet',
    'W6': 'Wizz Air', 'V7': 'Volotea', 'IB': 'Iberia',
    'UX': 'Air Europa', 'LS': 'Jet2', 'TOM': 'TUI',
    'LH': 'Lufthansa', 'BA': 'British Airways', 'AF': 'Air France',
    'KL': 'KLM', 'VS': 'Virgin Atlantic', 'TP': 'TAP',
    'AH': 'Air Algérie', 'AT': 'Royal Air Maroc', 'A3': 'Aegean',
    'SK': 'SAS', 'DY': 'Norwegian', 'EI': 'Aer Lingus',
    'EW': 'Eurowings', 'HV': 'Transavia', 'TO': 'Transavia France',
    'PC': 'Pegasus', 'TK': 'Turkish Airlines', 'OS': 'Austrian',
    'LX': 'Swiss', 'SN': 'Brussels Airlines', 'BT': 'Air Baltic',
    'FR': 'Ryanair', 'RK': 'Ryanair UK', 'EN': 'Air Dolomiti',
}

AIRLINE_EMOJIS = {
    'FR': '🟡', 'VY': '🔵', 'U2': '🟠', 'W6': '🟣',
    'V7': '🟢', 'IB': '🔴', 'UX': '🔵', 'LS': '🔵',
}


def get_amadeus_client():
    return Client(
        client_id=os.environ.get("AMADEUS_API_KEY"),
        client_secret=os.environ.get("AMADEUS_API_SECRET"),
    )


async def search_flights(origin, destination, date_out, date_in=None, passengers=1):
    def _search():
        client = get_amadeus_client()
        params = {
            'originLocationCode': origin,
            'destinationLocationCode': destination,
            'departureDate': date_out,
            'adults': 1,
            'max': 20,
            'currencyCode': 'EUR',
        }
        if date_in:
            params['returnDate'] = date_in
        response = client.shopping.flight_offers_search.get(**params)
        return response.data

    try:
        flights = await asyncio.get_event_loop().run_in_executor(None, _search)
        available = [
            f for f in flights
            if f.get('numberOfBookableSeats', 0) >= passengers
        ]
        available.sort(key=lambda x: float(x['price']['total']))
        return available[:5]
    except ResponseError as e:
        logger.error(f"Amadeus error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return []


def build_deeplink(airline_code, origin, destination, date_out, date_in, passengers):
    links = {
        'FR': (
            f"https://www.ryanair.com/es/es/trip/flights/select"
            f"?adults={passengers}&teens=0&children=0&infants=0"
            f"&dateOut={date_out}&originIata={origin}&destinationIata={destination}"
            f"{'&dateIn=' + date_in + '&isConnectedFlight=false&discount=0&isReturn=true' if date_in else '&isReturn=false'}"
        ),
        'VY': (
            f"https://www.vueling.com/es/compra-tus-vuelos/busca-tu-vuelo"
            f"?departureStation={origin}&arrivalStation={destination}"
            f"&outboundDate={date_out}&adt={passengers}&chd=0&inf=0"
            f"{'&inboundDate=' + date_in if date_in else ''}"
        ),
        'U2': (
            f"https://www.easyjet.com/es/vuelos-baratos/{origin.lower()}/{destination.lower()}"
            f"?departDate={date_out}&adults={passengers}&children=0&infants=0"
        ),
        'W6': (
            f"https://wizzair.com/es-es/booking/select-flight/{origin}/{destination}/{date_out}"
            f"/{date_in or 'null'}/{passengers}/0/0/null"
        ),
        'V7': (
            f"https://www.volotea.com/es/vuelos/{origin.lower()}/{destination.lower()}/"
            f"?adults={passengers}&departure={date_out}"
        ),
    }
    # Google Flights URL correcta
    if date_in:
        default = f"https://www.google.com/travel/flights/search?hl=es&q=vuelos+{origin}+{destination}+{date_out}+vuelta+{date_in}+{passengers}+pasajeros"
    else:
        default = f"https://www.google.com/travel/flights/search?hl=es&q=vuelos+{origin}+{destination}+{date_out}+{passengers}+pasajeros"

    return links.get(airline_code, default)


def format_duration(duration_str):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration_str)
    if not match:
        return duration_str
    hours = int(match.group(1) or 0)
    mins = int(match.group(2) or 0)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}min")
    return ' '.join(parts)


def format_flight_message(flights, origin, destination, date_out, date_in, passengers):
    """
    Devuelve lista de (mensaje, airline_name, deeplink_url).
    El teclado se construye en bot.py donde InlineKeyboardButton está importado.
    """
    results = []
    trip_type = "ida y vuelta" if date_in else "solo ida"

    for i, flight in enumerate(flights, 1):
        airline_code = flight.get('validatingAirlineCodes', ['??'])[0]
        airline_name = AIRLINE_NAMES.get(airline_code, airline_code)
        emoji = AIRLINE_EMOJIS.get(airline_code, '✈️')
        price_per_person = float(flight['price']['total'])
        price_total = price_per_person * passengers
        seats = flight.get('numberOfBookableSeats', '?')

        outbound = flight['itineraries'][0]
        out_segments = outbound['segments']
        out_dep = out_segments[0]['departure']
        out_arr = out_segments[-1]['arrival']
        out_duration = format_duration(outbound['duration'])
        out_stops = len(out_segments) - 1
        out_stops_txt = "Directo" if out_stops == 0 else f"{out_stops} escala{'s' if out_stops > 1 else ''}"
        dep_time = out_dep['at'][11:16]
        arr_time = out_arr['at'][11:16]

        msg = (
            f"{emoji} *Opción {i} — {airline_name}*\n"
            f"{'─' * 28}\n"
            f"🛫 `{origin}` {dep_time} → `{destination}` {arr_time}\n"
            f"⏱ {out_duration} · {out_stops_txt}\n"
        )

        if date_in and len(flight['itineraries']) > 1:
            inbound = flight['itineraries'][1]
            in_segments = inbound['segments']
            in_dep = in_segments[0]['departure']
            in_arr = in_segments[-1]['arrival']
            in_duration = format_duration(inbound['duration'])
            in_stops = len(in_segments) - 1
            in_stops_txt = "Directo" if in_stops == 0 else f"{in_stops} escala{'s' if in_stops > 1 else ''}"
            in_dep_time = in_dep['at'][11:16]
            in_arr_time = in_arr['at'][11:16]
            msg += (
                f"🛬 `{destination}` {in_dep_time} → `{origin}` {in_arr_time}\n"
                f"⏱ {in_duration} · {in_stops_txt}\n"
            )

        msg += (
            f"{'─' * 28}\n"
            f"💶 *{price_per_person:.0f}€/persona* · Total grupo: *{price_total:.0f}€*\n"
            f"💺 {seats} plazas disponibles ({trip_type})"
        )

        deeplink = build_deeplink(airline_code, origin, destination, date_out, date_in, passengers)
        results.append((msg, airline_name, deeplink))

    return results
