import os
from sqlalchemy.orm import Session
import models
from security import obtener_password_hash

# Catálogo con rangos reales de años en México: [año_inicio, año_fin]
CATALOGO_VEHICULOS_MX = {
    "Acura": {
        "ILX":, "Integra":, "MDX":,
        "RDX":, "TLX":, "TSX": [2004, 2014]
    },
    "Alfa Romeo": {
        "Giulia":, "Giulietta":,
        "Mito":, "Stelvio": [2018, 2026]
    },
    "Audi": {
        "A1":, "A3":, "A4":,
        "A5":, "A6":, "Q2":,
        "Q3":, "Q5":, "Q7":,
        "TT": [1999, 2023]
    },
    "BMW": {
        "Serie 1":, "Serie 3":, "Serie 4":,
        "Serie 5":, "X1":, "X3":,
        "X4":, "X5":, "X6": [2008, 2026]
    },
    "Buick": {
        "Encore":, "Envision":, "LaCrosse":,
        "Regal":, "Verano": [2012, 2017]
    },
    "BYD": {
        "Dolphin":, "Dolphin Mini":, "Han":,
        "King":, "Song Plus":, "Tang":,
        "Yuan Plus": [2023, 2026]
    },
    "Cadillac": {
        "ATS":, "CTS":, "DeVille":,
        "Escalade":, "SRX":, "XT4":,
        "XT5": [2017, 2026]
    },
    "Changan": {
        "Alsvin":, "CS15":, "CS35 Plus":,
        "CS55 Plus":, "UNI-K": [2022, 2026]
    },
    "Chevrolet": {
        "Aveo":, "Beat":, "Captiva":,
        "Cavalier":, "Chevy":, "Chevy C2":,
        "Cheyenne":, "Cruze":, "Equinox":,
        "Impala":, "Lumina":, "Malibu":,
        "Monza":, "Onix":, "Optra":,
        "S10":, "Silverado":, "Sonic":,
        "Spark":, "Suburban":, "Tahoe":,
        "Tornado":, "Tracker":, "Trax": [2013, 2026]
    },
    "Chrysler": {
        "300C":, "Cirrus":, "LeBaron":,
        "Neon":, "Pacifica":, "PT Cruiser":,
        "Sebring":, "Town & Country":, "Voyager": [1988, 2022]
    },
    "Cupra": {
        "Ateca":, "Born":, "Formentor":,
        "Leon": [2021, 2026]
    },
    "Dacia": {
        "Duster":, "Logan":, "Sandero":,
        "Stepway": [2010, 2026]
    },
    "Dodge": {
        "Atos":, "Attitude":, "Avenger":,
        "Caliber":, "Caravan":, "Dart":,
        "Durango":, "Grand Caravan":, "Journey":,
        "Neon":, "Ram Charger":, "Stratus":,
        "Verna": [2004, 2006]
    },
    "Fiat": {
        "500":, "Argo":, "Ducato":,
        "Fastback":, "Idea":, "Mobi":,
        "Palio":, "Pulse":, "Siena":,
        "Stilo":, "Uno": [2011, 2022]
    },
    "Ford": {
        "Courier":, "EcoSport":, "Edge":,
        "Escape":, "Expedition":, "Explorer":,
        "F-150":, "Fiesta":, "Fiesta Ikon":,
        "Figo":, "Focus":, "Freestar":,
        "Fusion":, "Ghia":, "Ka":,
        "Lobo":, "Mustang":, "Ranger":,
        "Topaz":, "Windstar": [1995, 2003]
    },
    "Geely": {
        "Coolray":, "Emgrand":, "Geometry C":,
        "Okavango":, "Starray": [2024, 2026]
    },
    "GMC": {
        "Acadia":, "Canyon":, "Envoy":,
        "Sierra":, "Terrain":, "Yukon": [1995, 2026]
    },
    "Honda": {
        "Accord":, "City":, "Civic":,
        "CR-V":, "Crosstour":, "Element":,
        "Fit":, "HR-V":, "Odyssey":,
        "Passport":, "Pilot": [2003, 2026]
    },
    "Hummer": {
        "H1":, "H2":, "H3": [2006, 2010]
    },
    "Hyundai": {
        "Accent":, "Creta":, "Elantra":,
        "Grand i10":, "ix35":, "Santa Fe":,
        "Sonata":, "Staria":, "Tucson":,
        "Verna": [2004, 2006]
    },
    "Infiniti": {
        "G35":, "G37":, "Q50":,
        "Q60":, "QX50":, "QX60":,
        "QX70":, "QX80": [2014, 2026]
    },
    "Isuzu": {
        "Amigo":, "D-Max":, "ELF":,
        "Rodeo": [1991, 2004]
    },
    "Jaguar": {
        "F-Pace":, "S-Type":, "X-Type":,
        "XE":, "XF": [2009, 2024]
    },
    "Jeep": {
        "Cherokee":, "Commander":, "Compass":,
        "Gladiator":, "Grand Cherokee":, "Liberty":,
        "Patriot":, "Renegade":, "Wrangler": [1987, 2026]
    },
    "Jetour": {
        "Dashing":, "X70":, "X70 Plus":,
        "X90 Plus": [2023, 2026]
    },
    "Kia": {
        "Forte":, "K3":, "Niro":,
        "Optima":, "Rio":, "Sedona":,
        "Seltos":, "Sonet":, "Sorento":,
        "Soul":, "Sportage": [2016, 2026]
    },
    "Land Rover": {
        "Defender":, "Discovery":, "Freelander":,
        "LR3":, "LR4":, "Range Rover Evoque": [2012, 2026]
    },
    "Lexus": {
        "ES":, "IS":, "LX":,
        "NX":, "RX":, "UX": [2022, 2026]
    },
    "Lincoln": {
        "Aviator":, "Corsair":, "MKS":,
        "MKX":, "MKZ":, "Nautilus":,
        "Navigator":, "Town Car": [1985, 2011]
    },
    "Mazda": {
        "CX-3":, "CX-30":, "CX-5":,
        "CX-50":, "CX-7":, "CX-9":,
        "Mazda 2":, "Mazda 3":, "Mazda 6":,
        "MX-5":, "Protege": [1995, 2003]
    },
    "Mercedes-Benz": {
        "Clase A":, "Clase B":, "Clase C":,
        "Clase E":, "GLA":, "GLC":,
        "GLE":, "ML":, "Sprinter": [2002, 2026]
    },
    "MG": {
        "GT":, "HS":, "MG3":,
        "MG5":, "ONE":, "RX5":,
        "ZS": [2021, 2026]
    },
    "Mini": {
        "Clubman":, "Cooper":, "Countryman":,
        "Paceman": [2013, 2016]
    },
    "Mitsubishi": {
        "Eclipse":, "Endeavor":, "Galant":,
        "L200":, "Lancer":, "Mirage":,
        "Mirage G4":, "Montero Sport":, "Outlander": [2003, 2026]
    },
    "Nissan": {
        "Altima":, "Aprio":, "Armada":,
        "D21":, "Estaquitas":, "Frontier":,
        "Hikari":, "Kicks":, "March":,
        "Maxima":, "Murano":, "Note":,
        "NP300":, "Pathfinder":, "Platina":,
        "Sentra":, "Tiida":, "Tsubame":,
        "Tsuru":, "Tsuru I":, "Tsuru II":,
        "Tsuru III":, "Urvan":, "Versa":,
        "X-Trail": [2002, 2026]
    },
    "Omoda": {
        "C5":, "O5":, "O5 GT": [2024, 2026]
    },
    "Peugeot": {
        "2008":, "206":, "207":,
        "208":, "3008":, "301":,
        "307":, "308":, "406":,
        "Manager":, "Partner":, "Rifter": [2020, 2026]
    },
    "Pontiac": {
        "Aztek":, "G3":, "G6":,
        "Grand Am":, "Grand Prix":, "Matiz":,
        "Solstice":, "Sunfire":, "Torrent": [2006, 2009]
    },
    "Porsche": {
        "911":, "Boxster":, "Cayenne":,
        "Cayman":, "Macan":, "Panamera": [2010, 2026]
    },
    "Ram": {
        "1500":, "2500":, "4000":,
        "700":, "Charger":, "ProMaster": [2014, 2026]
    },
    "Renault": {
        "Captur":, "Clio":, "Duster":,
        "Fluence":, "Kangoo":, "Koleos":,
        "Kwid":, "Logan":, "Megane":,
        "Oroch":, "Platina":, "Scenic":,
        "Stepway": [2010, 2026]
    },
    "Scion": {
        "tC":, "xA":, "xB": [2004, 2015]
    },
    "Seat": {
        "Altea":, "Arona":, "Ateca":,
        "Cordoba":, "Freetrack":, "Ibiza":,
        "Leon":, "Tarraco":, "Toledo": [2001, 2019]
    },
    "Smart": {
        "Forfour":, "Fortwo":, "Roadster": [2003, 2005]
    },
    "Subaru": {
        "BRZ":, "Forester":, "Impreza":,
        "Outback":, "WRX":, "XV": [2013, 2023]
    },
    "Suzuki": {
        "Aerio":, "Ciaz":, "Ertiga":,
        "Grand Vitara":, "Ignis":, "Jimny":,
        "S-Cross":, "Swift":, "SX4":,
        "Vitara": [2016, 2026]
    },
    "Toyota": {
        "Avanza":, "Camry":, "Celica":,
        "Corolla":, "Corona":, "Hiace":,
        "Hilux":, "Matrix":, "Prius":,
        "RAV4":, "Sienna":, "Tacoma":,
        "Tundra":, "Yaris": [2006, 2026]
    },
    "Volkswagen": {
        "Amarok":, "Beetle":, "Bora":,
        "Clasico":, "Combi":, "Corsar":,
        "Crafter":, "CrossFox":, "Derby":,
        "Eurovan":, "Gol":, "Golf":,
        "Golf A4":, "Jetta":, "Jetta A3":,
        "Jetta A4":, "Lupo":, "Passat":,
        "Pointer":, "Polo":, "Saveiro":,
        "Sedan (Vocho)":, "Sharan":, "Taos":,
        "Tiguan":, "Transporter":, "Vento": [2014, 2022]
    },
    "Volvo": {
        "C30":, "S40":, "S60":,
        "V40":, "XC40":, "XC60":,
        "XC90": [2003, 2026]
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
