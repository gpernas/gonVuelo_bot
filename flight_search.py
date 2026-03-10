import logging
import re
import asyncio
from fast_flights import FlightData, Passengers, get_flights

logger = logging.getLogger(__name__)

AIRLINE_EMOJIS = {
    'Ryanair': '🟡', 'Vueling': '🔵', 'easyJet': '🟠', 'Wizz Air': '🟣',
    'Volotea': '🟢', 'Iberia': '🔴', 'Air Europa': '🔵', 'Jet2': '🔵',
    'Transavia': '🟤', 'Norwegian': '🩵', 'TUI': '🟩',
}


async def search_flights(origin, destination, date_out, date_in=None, passengers=1):
    """
    Busca vuelos con Google Flights (fast-flights).
    Devuelve lista de vuelos ordenados por precio.
    """
    def _search():
        try:
            result = get_flights(
                flight_data=[FlightData(
                    date=date_out,
                    from_airport=origin,
                    to_airport=destination,
                )],
                trip="round-trip" if date_in else "one-way",
                seat="economy",
                passengers=Passengers(adults=1),  # buscamos 1 para ver disponibilidad
                fetch_mode="fallback",
            )
            return result
        except Exception as e:
            logger.error(f"Error buscando vuelos: {e}")
            return None

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _search)
        if not result or not result.flights:
            return []

        # Filtramos y ordenamos por precio
        flights = [f for f in result.flights if f.price]
        flights.sort(key=lambda x: _parse_price(x.price))
        return flights[:5]

    except Exception as e:
        logger.error(f"Error en search_flights: {e}")
        return []


def _parse_price(price_str):
    """Extrae el número de un string de precio como '58 €' o '€58'"""
    if not price_str:
        return 99999
    nums = re.findall(r'\d+', price_str.replace(',', ''))
    return int(nums[0]) if nums else 99999


def build_deeplink(airline_name, origin, destination, date_out, date_in, passengers):
    """Genera deep links directos a cada aerolínea."""
    name = airline_name.lower()
    if 'ryanair' in name:
        return (
            f"https://www.ryanair.com/es/es/trip/flights/select"
            f"?adults={passengers}&teens=0&children=0&infants=0"
            f"&dateOut={date_out}&originIata={origin}&destinationIata={destination}"
            f"{'&dateIn=' + date_in + '&isReturn=true' if date_in else '&isReturn=false'}"
        )
    elif 'vueling' in name:
        return (
            f"https://www.vueling.com/es/compra-tus-vuelos/busca-tu-vuelo"
            f"?departureStation={origin}&arrivalStation={destination}"
            f"&outboundDate={date_out}&adt={passengers}&chd=0&inf=0"
            f"{'&inboundDate=' + date_in if date_in else ''}"
        )
    elif 'easyjet' in name:
        return (
            f"https://www.easyjet.com/es/vuelos-baratos/{origin.lower()}/{destination.lower()}"
            f"?departDate={date_out}&adults={passengers}"
        )
    elif 'wizz' in name:
        return (
            f"https://wizzair.com/es-es/booking/select-flight"
            f"/{origin}/{destination}/{date_out}/{date_in or 'null'}/{passengers}/0/0/null"
        )
    elif 'volotea' in name:
        return (
            f"https://www.volotea.com/es/vuelos/{origin.lower()}/{destination.lower()}/"
            f"?adults={passengers}&departure={date_out}"
        )
    elif 'iberia' in name:
        return (
            f"https://www.iberia.com/es/vuelos/?origin={origin}&destination={destination}"
            f"&departureDate={date_out}&adults={passengers}&cabin=N"
        )
    else:
        # Fallback: Google Flights con parámetros reales
        trip = f"{origin}.{destination}.{date_out}"
        if date_in:
            trip += f"*{destination}.{origin}.{date_in}"
        return f"https://www.google.com/travel/flights/search?tfs=&hl=es&curr=EUR&q=vuelos+{origin}+{destination}+{date_out}"


def format_flight_message(flights, origin, destination, date_out, date_in, passengers):
    """
    Devuelve lista de (mensaje, airline_name, deeplink_url).
    """
    results = []
    trip_type = "ida y vuelta" if date_in else "solo ida"

    for i, flight in enumerate(flights, 1):
        airline = flight.name or "Aerolínea"
        emoji = AIRLINE_EMOJIS.get(airline, '✈️')
        price_unit = _parse_price(flight.price)
        price_total = price_unit * passengers
        stops = flight.stops or 0
        stops_txt = "Directo" if stops == 0 else f"{stops} escala{'s' if stops > 1 else ''}"
        duration = flight.duration or "?"

        # Horarios
        dep_time = flight.departure or "?"
        arr_time = flight.arrival or "?"
        ahead = f" (+{flight.arrival_time_ahead})" if getattr(flight, 'arrival_time_ahead', None) else ""

        msg = (
            f"{emoji} *Opción {i} — {airline}*\n"
            f"{'─' * 28}\n"
            f"🛫 `{origin}` {dep_time} → `{destination}` {arr_time}{ahead}\n"
            f"⏱ {duration} · {stops_txt}\n"
            f"{'─' * 28}\n"
            f"💶 *{price_unit}€/persona* · Total grupo: *{price_total}€*\n"
            f"📊 Precio {flight.current_price if hasattr(flight, 'current_price') else 'disponible'} · {trip_type}"
        )

        deeplink = build_deeplink(airline, origin, destination, date_out, date_in, passengers)
        results.append((msg, airline, deeplink))

    return results
