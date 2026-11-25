import os
from sqlalchemy.orm import Session
import models
from security import obtener_password_hash
# Catálogo con rangos reales de años en México: (año_inicio, año_fin)
CATALOGO_VEHICULOS_MX = {
    "Acura": {
        "ILX": (2013, 2022),
        "Integra": (2023, 2026),
        "MDX": (2004, 2026),
        "RDX": (2007, 2026),
        "TLX": (2015, 2025),
        "TSX": (2004, 2014)
    },
    "Alfa Romeo": {
        "Giulia": (2017, 2026),
        "Giulietta": (2012, 2020),
        "Mito": (2010, 2018),
        "Stelvio": (2018, 2026)
    },
    "Audi": {
        "A1": (2011, 2026),
        "A3": (1998, 2026),
        "A4": (1997, 2025),
        "A5": (2008, 2026),
        "A6": (1998, 2026),
        "Q2": (2017, 2026),
        "Q3": (2012, 2026),
        "Q5": (2009, 2026),
        "Q7": (2006, 2026),
        "TT": (1999, 2023)
    },
    "BMW": {
        "Serie 1": (2005, 2026),
        "Serie 3": (1994, 2026),
        "Serie 4": (2014, 2026),
        "Serie 5": (1995, 2026),
        "X1": (2010, 2026),
        "X3": (2004, 2026),
        "X4": (2015, 2026),
        "X5": (2000, 2026),
        "X6": (2008, 2026)
    },
    "Buick": {
        "Encore": (2013, 2022),
        "Envision": (2016, 2026),
        "LaCrosse": (2010, 2019),
        "Regal": (2011, 2017),
        "Verano": (2012, 2017)
    },
    "BYD": {
        "Dolphin": (2023, 2026),
        "Dolphin Mini": (2024, 2026),
        "Han": (2023, 2026),
        "King": (2024, 2026),
        "Song Plus": (2023, 2026),
        "Tang": (2023, 2026),
        "Yuan Plus": (2023, 2026)
    },
    "Cadillac": {
        "ATS": (2013, 2019),
        "CTS": (2003, 2019),
        "DeVille": (1994, 2005),
        "Escalade": (1999, 2026),
        "SRX": (2004, 2016),
        "XT4": (2019, 2026),
        "XT5": (2017, 2026)
    },
    "Changan": {
        "Alsvin": (2022, 2026),
        "CS15": (2022, 2025),
        "CS35 Plus": (2022, 2026),
        "CS55 Plus": (2022, 2026),
        "UNI-K": (2022, 2026)
    },
    "Chevrolet": {
        "Aveo": (2008, 2026),
        "Beat": (2018, 2021),
        "Captiva": (2008, 2026),
        "Cavalier": (1990, 2024),
        "Chevy": (1994, 2012),
        "Chevy C2": (2004, 2008),
        "Cheyenne": (1985, 2026),
        "Cruze": (2010, 2018),
        "Equinox": (2005, 2026),
        "Impala": (2000, 2016),
        "Lumina": (1990, 2001),
        "Malibu": (1997, 2024),
        "Monza": (1996, 2012),
        "Onix": (2020, 2026),
        "Optra": (2006, 2010),
        "S10": (1991, 2026),
        "Silverado": (1995, 2026),
        "Sonic": (2012, 2017),
        "Spark": (2011, 2021),
        "Suburban": (1985, 2026),
        "Tahoe": (1995, 2026),
        "Tornado": (2004, 2026),
        "Tracker": (1998, 2026),
        "Trax": (2013, 2026)
    },
    "Chrysler": {
        "300C": (2005, 2016),
        "Cirrus": (1995, 2010),
        "LeBaron": (1985, 1995),
        "Neon": (1995, 2005),
        "Pacifica": (2004, 2026),
        "PT Cruiser": (2001, 2010),
        "Sebring": (1996, 2010),
        "Town & Country": (1990, 2016),
        "Voyager": (1988, 2022)
    },
    "Cupra": {
        "Ateca": (2020, 2026),
        "Born": (2023, 2026),
        "Formentor": (2021, 2026),
        "Leon": (2021, 2026)
    },
    "Dacia": {
        "Duster": (2010, 2026),
        "Logan": (2005, 2026),
        "Sandero": (2008, 2026),
        "Stepway": (2010, 2026)
    },
    "Dodge": {
        "Atos": (2001, 2012),
        "Attitude": (2006, 2026),
        "Avenger": (2008, 2014),
        "Caliber": (2007, 2012),
        "Caravan": (1988, 2007),
        "Dart": (2013, 2016),
        "Durango": (1998, 2026),
        "Grand Caravan": (1988, 2020),
        "Journey": (2009, 2026),
        "Neon": (1995, 2020),
        "Ram Charger": (1985, 2001),
        "Stratus": (1995, 2006),
        "Verna": (2004, 2006)
    },
    "Fiat": {
        "500": (2009, 2024),
        "Argo": (2021, 2026),
        "Ducato": (2007, 2026),
        "Fastback": (2023, 2026),
        "Idea": (2007, 2010),
        "Mobi": (2017, 2026),
        "Palio": (2004, 2020),
        "Pulse": (2022, 2026),
        "Siena": (2005, 2012),
        "Stilo": (2003, 2008),
        "Uno": (2011, 2022)
    },
    "Ford": {
        "Courier": (2001, 2012),
        "EcoSport": (2004, 2022),
        "Edge": (2007, 2024),
        "Escape": (2001, 2026),
        "Expedition": (1997, 2026),
        "Explorer": (1991, 2026),
        "F-150": (1985, 2026),
        "Fiesta": (1998, 2019),
        "Fiesta Ikon": (2001, 2015),
        "Figo": (2016, 2021),
        "Focus": (2000, 2018),
        "Freestar": (2004, 2007),
        "Fusion": (2006, 2020),
        "Ghia": (1991, 1994),
        "Ka": (2001, 2008),
        "Lobo": (1997, 2026),
        "Mustang": (1985, 2026),
        "Ranger": (1990, 2026),
        "Topaz": (1984, 1994),
        "Windstar": (1995, 2003)
    },
    "Geely": {
        "Coolray": (2024, 2026),
        "Emgrand": (2024, 2026),
        "Geometry C": (2024, 2026),
        "Okavango": (2024, 2026),
        "Starray": (2024, 2026)
    },
    "GMC": {
        "Acadia": (2007, 2026),
        "Canyon": (2004, 2026),
        "Envoy": (2002, 2009),
        "Sierra": (1995, 2026),
        "Terrain": (2010, 2026),
        "Yukon": (1995, 2026)
    },
    "Honda": {
        "Accord": (1995, 2026),
        "City": (2010, 2026),
        "Civic": (1995, 2026),
        "CR-V": (1997, 2026),
        "Crosstour": (2010, 2015),
        "Element": (2003, 2011),
        "Fit": (2006, 2020),
        "HR-V": (2016, 2026),
        "Odyssey": (1995, 2026),
        "Passport": (1994, 2026),
        "Pilot": (2003, 2026)
    },
    "Hummer": {
        "H1": (1992, 2006),
        "H2": (2003, 2009),
        "H3": (2006, 2010)
    },
    "Hyundai": {
        "Accent": (2018, 2022),
        "Creta": (2016, 2026),
        "Elantra": (2014, 2026),
        "Grand i10": (2015, 2026),
        "ix35": (2014, 2015),
        "Santa Fe": (2014, 2026),
        "Sonata": (2014, 2025),
        "Staria": (2022, 2026),
        "Tucson": (2016, 2026),
        "Verna": (2004, 2006)
    },
    "Infiniti": {
        "G35": (2003, 2008),
        "G37": (2008, 2013),
        "Q50": (2014, 2024),
        "Q60": (2014, 2022),
        "QX50": (2014, 2026),
        "QX60": (2014, 2026),
        "QX70": (2014, 2017),
        "QX80": (2014, 2026)
    },
    "Isuzu": {
        "Amigo": (1989, 2000),
        "D-Max": (2005, 2026),
        "ELF": (2007, 2026),
        "Rodeo": (1991, 2004)
    },
    "Jaguar": {
        "F-Pace": (2017, 2025),
        "S-Type": (2000, 2008),
        "X-Type": (2002, 2009),
        "XE": (2016, 2020),
        "XF": (2009, 2024)
    },
    "Jeep": {
        "Cherokee": (1985, 2023),
        "Commander": (2006, 2010),
        "Compass": (2007, 2026),
        "Gladiator": (2020, 2026),
        "Grand Cherokee": (1993, 2026),
        "Liberty": (2002, 2012),
        "Patriot": (2007, 2017),
        "Renegade": (2017, 2026),
        "Wrangler": (1987, 2026)
    },
    "Jetour": {
        "Dashing": (2023, 2026),
        "X70": (2023, 2026),
        "X70 Plus": (2023, 2026),
        "X90 Plus": (2023, 2026)
    },
    "Kia": {
        "Forte": (2016, 2024),
        "K3": (2024, 2026),
        "Niro": (2017, 2026),
        "Optima": (2016, 2020),
        "Rio": (2016, 2023),
        "Sedona": (2016, 2021),
        "Seltos": (2020, 2026),
        "Sonet": (2024, 2026),
        "Sorento": (2016, 2026),
        "Soul": (2016, 2026),
        "Sportage": (2016, 2026)
    },
    "Land Rover": {
        "Defender": (1993, 2026),
        "Discovery": (1994, 2026),
        "Freelander": (2001, 2015),
        "LR3": (2005, 2009),
        "LR4": (2010, 2016),
        "Range Rover Evoque": (2012, 2026)
    },
    "Lexus": {
        "ES": (2022, 2026),
        "IS": (2022, 2026),
        "LX": (2022, 2026),
        "NX": (2022, 2026),
        "RX": (2022, 2026),
        "UX": (2022, 2026)
    },
    "Lincoln": {
        "Aviator": (2003, 2026),
        "Corsair": (2020, 2026),
        "MKS": (2009, 2016),
        "MKX": (2007, 2018),
        "MKZ": (2007, 2020),
        "Nautilus": (2019, 2026),
        "Navigator": (1998, 2026),
        "Town Car": (1985, 2011)
    },
    "Mazda": {
        "CX-3": (2016, 2026),
        "CX-30": (2020, 2026),
        "CX-5": (2013, 2026),
        "CX-50": (2023, 2026),
        "CX-7": (2007, 2012),
        "CX-9": (2007, 2023),
        "Mazda 2": (2011, 2026),
        "Mazda 3": (2006, 2026),
        "Mazda 6": (2004, 2021),
        "MX-5": (2006, 2026),
        "Protege": (1995, 2003)
    },
    "Mercedes-Benz": {
        "Clase A": (2001, 2026),
        "Clase B": (2006, 2019),
        "Clase C": (1994, 2026),
        "Clase E": (1994, 2026),
        "GLA": (2015, 2026),
        "GLC": (2016, 2026),
        "GLE": (2016, 2026),
        "ML": (1998, 2015),
        "Sprinter": (2002, 2026)
    },
    "MG": {
        "GT": (2022, 2026),
        "HS": (2021, 2026),
        "MG3": (2024, 2026),
        "MG5": (2021, 2026),
        "ONE": (2024, 2026),
        "RX5": (2023, 2026),
        "ZS": (2021, 2026)
    },
    "Mini": {
        "Clubman": (2008, 2024),
        "Cooper": (2002, 2026),
        "Countryman": (2011, 2026),
        "Paceman": (2013, 2016)
    },
    "Mitsubishi": {
        "Eclipse": (1995, 2026),
        "Endeavor": (2004, 2011),
        "Galant": (2004, 2012),
        "L200": (2008, 2026),
        "Lancer": (2004, 2017),
        "Mirage": (2015, 2020),
        "Mirage G4": (2017, 2026),
        "Montero Sport": (2000, 2026),
        "Outlander": (2003, 2026)
    },
    "Nissan": {
        "Altima": (1995, 2026),
        "Aprio": (2008, 2010),
        "Armada": (2004, 2026),
        "D21": (1986, 2008),
        "Estaquitas": (1985, 2015),
        "Frontier": (1998, 2026),
        "Hikari": (1988, 1992),
        "Kicks": (2017, 2026),
        "March": (2012, 2026),
        "Maxima": (1995, 2023),
        "Murano": (2003, 2026),
        "Note": (2014, 2019),
        "NP300": (2009, 2026),
        "Pathfinder": (1990, 2026),
        "Platina": (2002, 2010),
        "Sentra": (1996, 2026),
        "Tiida": (2007, 2018),
        "Tsubame": (1993, 2004),
        "Tsuru": (1984, 2017),
        "Tsuru I": (1984, 1987),
        "Tsuru II": (1988, 1991),
        "Tsuru III": (1992, 2017),
        "Urvan": (2000, 2026),
        "Versa": (2012, 2026),
        "X-Trail": (2002, 2026)
    },
    "Omoda": {
        "C5": (2023, 2026),
        "O5": (2023, 2026),
        "O5 GT": (2024, 2026)
    },
    "Peugeot": {
        "2008": (2014, 2026),
        "206": (2000, 2009),
        "207": (2007, 2014),
        "208": (2013, 2026),
        "3008": (2011, 2026),
        "301": (2013, 2024),
        "307": (2002, 2010),
        "308": (2009, 2026),
        "406": (1998, 2004),
        "Manager": (2008, 2026),
        "Partner": (2004, 2026),
        "Rifter": (2020, 2026)
    },
    "Pontiac": {
        "Aztek": (2001, 2005),
        "G3": (2007, 2009),
        "G6": (2005, 2009),
        "Grand Am": (1995, 2005),
        "Grand Prix": (1995, 2008),
        "Matiz": (2004, 2015),
        "Solstice": (2006, 2009),
        "Sunfire": (1995, 2005),
        "Torrent": (2006, 2009)
    },
    "Porsche": {
        "911": (1985, 2026),
        "Boxster": (1997, 2026),
        "Cayenne": (2003, 2026),
        "Cayman": (2006, 2026),
        "Macan": (2014, 2026),
        "Panamera": (2010, 2026)
    },
    "Ram": {
        "1500": (1994, 2026),
        "2500": (1994, 2026),
        "4000": (1994, 2026),
        "700": (2015, 2026),
        "Charger": (2006, 2023),
        "ProMaster": (2014, 2026)
    },
    "Renault": {
        "Captur": (2018, 2024),
        "Clio": (2002, 2010),
        "Duster": (2012, 2026),
        "Fluence": (2011, 2017),
        "Kangoo": (2004, 2026),
        "Koleos": (2009, 2026),
        "Kwid": (2019, 2026),
        "Logan": (2015, 2026),
        "Megane": (2001, 2010),
        "Oroch": (2018, 2026),
        "Platina": (2002, 2010),
        "Scenic": (2001, 2008),
        "Stepway": (2010, 2026)
    },
    "Scion": {
        "tC": (2005, 2016),
        "xA": (2004, 2006),
        "xB": (2004, 2015)
    },
    "Seat": {
        "Altea": (2005, 2015),
        "Arona": (2018, 2026),
        "Ateca": (2017, 2026),
        "Cordoba": (2001, 2009),
        "Freetrack": (2008, 2015),
        "Ibiza": (2001, 2026),
        "Leon": (2001, 2026),
        "Tarraco": (2019, 2025),
        "Toledo": (2001, 2019)
    },
    "Smart": {
        "Forfour": (2005, 2019),
        "Fortwo": (2001, 2019),
        "Roadster": (2003, 2005)
    },
    "Subaru": {
        "BRZ": (2013, 2026),
        "Forester": (2006, 2026),
        "Impreza": (2006, 2026),
        "Outback": (2006, 2026),
        "WRX": (2006, 2026),
        "XV": (2013, 2023)
    },
    "Suzuki": {
        "Aerio": (2006, 2007),
        "Ciaz": (2016, 2024),
        "Ertiga": (2019, 2026),
        "Grand Vitara": (2006, 2026),
        "Ignis": (2017, 2026),
        "Jimny": (2021, 2026),
        "S-Cross": (2014, 2026),
        "Swift": (2007, 2026),
        "SX4": (2008, 2014),
        "Vitara": (2016, 2026)
    },
    "Toyota": {
        "Avanza": (2007, 2026),
        "Camry": (2002, 2026),
        "Celica": (2002, 2005),
        "Corolla": (2002, 2026),
        "Corona": (1985, 2001),
        "Hiace": (2005, 2026),
        "Hilux": (2004, 2026),
        "Matrix": (2003, 2010),
        "Prius": (2010, 2026),
        "RAV4": (2002, 2026),
        "Sienna": (2002, 2026),
        "Tacoma": (2005, 2026),
        "Tundra": (2007, 2026),
        "Yaris": (2006, 2026)
    },
    "Volkswagen": {
        "Amarok": (2011, 2026),
        "Beetle": (1998, 2019),
        "Bora": (2006, 2010),
        "Clasico": (2011, 2015),
        "Combi": (1970, 2001),
        "Corsar": (1984, 1988),
        "Crafter": (2008, 2026),
        "CrossFox": (2007, 2017),
        "Derby": (1995, 2009),
        "Eurovan": (2001, 2009),
        "Gol": (2009, 2020),
        "Golf": (1987, 2026),
        "Golf A4": (2000, 2007),
        "Jetta": (1987, 2026),
        "Jetta A3": (1993, 1999),
        "Jetta A4": (1999, 2015),
        "Lupo": (2005, 2009),
        "Passat": (1991, 2022),
        "Pointer": (1998, 2010),
        "Polo": (2003, 2026),
        "Saveiro": (2010, 2026),
        "Sedan (Vocho)": (1954, 2003),
        "Sharan": (2002, 2008),
        "Taos": (2021, 2026),
        "Tiguan": (2009, 2026),
        "Transporter": (2010, 2026),
        "Vento": (2014, 2022)
    },
    "Volvo": {
        "C30": (2007, 2013),
        "S40": (2000, 2012),
        "S60": (2001, 2026),
        "V40": (2000, 2019),
        "XC40": (2018, 2026),
        "XC60": (2009, 2026),
        "XC90": (2003, 2026)
    }
}

# Diccionarios ordenados alfabéticamente (A-Z) listos para el frontend
DICCIONARIO_VEHICULOS = {
    marca: sorted(modelos.keys(), key=lambda x: x.lower())
    for marca, modelos in sorted(CATALOGO_VEHICULOS_MX.items(), key=lambda item: item[0].lower())
}

RANGOS_MODELOS_MX = {
    marca: {modelo: modelos[modelo] for modelo in sorted(modelos.keys(), key=lambda x: x.lower())}
    for marca, modelos in sorted(CATALOGO_VEHICULOS_MX.items(), key=lambda item: item[0].lower())
}

GRUPOS_ANOS = [str(anio) for anio in range(2026, 1966, -1)]

def seed_database(db: Session):
    """Inicializa el Administrador raíz de forma segura"""
    try:
        admin = db.query(models.Usuario).filter(models.Usuario.usuario == "admin").first()
        if not admin:
            password_segura = os.getenv("ADMIN_INITIAL_PASSWORD", "AdminCorp2026*")
            new_admin = models.Usuario(
                nombre="Administrador General",
                usuario="admin",
                contrasena_hash=obtener_password_hash(password_segura[:72]),
                rol=models.RolEnum.Administrador,
                telefono_celular="+529980000000"
            )
            db.add(new_admin)
            db.commit()
            print("[SEED] Usuario Administrador raíz creado exitosamente.")
    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] Fallo durante la precarga: {str(e)}")
        raise e
