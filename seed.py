# seed.py
from sqlalchemy.orm import Session
import models
from security import obtener_password_hash

DICCIONARIO_VEHICULOS = {
    "Acura": ["ILX", "MDX", "TLX", "RDX", "TSX", "Integra"],
    "Alfa Romeo": ["Giulia", "Stelvio", "Giulietta", "Mito"],
    "Audi": ["A1", "A3", "A4", "A5", "A6", "Q2", "Q3", "Q5", "Q7", "TT"],
    "BMW": ["Serie 1", "Serie 3", "Serie 4", "Serie 5", "X1", "X3", "X4", "X5", "X6"],
    "Buick": ["Encore", "Envision", "LaCrosse", "Regal", "Verano"],
    "BYD": ["Dolphin", "Tang", "Han", "Yuan Plus", "Song Plus", "King"],
    "Cadillac": ["CTS", "ATS", "Escalade", "SRX", "XT4", "XT5", "DeVille"],
    "Changan": ["Alsvin", "CS15", "CS35 Plus", "CS55 Plus", "UNI-K"],
    "Chevrolet": ["Chevy", "Chevy C2", "Aveo", "Optra", "Spark", "Beat", "Onix", "Cruze", "Sonic", "Cavalier", "Malibu", "Impala", "Captiva", "Trax", "Tracker", "Equinox", "Suburban", "Tahoe", "Silverado", "Cheyenne", "S10", "Lumina", "Monza", "Tornado"],
    "Chrysler": ["Pacifica", "Town & Country", "300C", "Voyager", "PT Cruiser", "Neon", "Cirrus", "Sebring", "LeBaron"],
    "Cupra": ["Formentor", "Leon", "Ateca", "Born"],
    "Dacia": ["Sandero", "Duster", "Logan", "Stepway"],
    "Dodge": ["Neon", "Attitude", "Journey", "Dart", "Durango", "Stratus", "Caravan", "Grand Caravan", "Ram Charger", "Caliber", "Avenger", "Verna", "Atos"],
    "Fiat": ["Pulse", "Mobi", "Uno", "500", "Palio", "Siena", "Stilo", "Ducato", "Argo", "Fastback"],
    "Ford": ["Fiesta", "Fiesta Ikon", "Focus", "Ka", "EcoSport", "Escape", "Explorer", "Expedition", "Ranger", "Mustang", "F-150", "Lobo", "Courier", "Fusion", "Figo", "Edge", "Windstar", "Freestar", "Ghia", "Topaz"],
    "Geely": ["Coolray", "Geometry C", "Emgrand", "Okavango", "Starray"],
    "GMC": ["Sierra", "Yukon", "Acadia", "Terrain", "Canyon", "Envoy"],
    "Honda": ["Civic", "Accord", "CR-V", "HR-V", "Fit", "Pilot", "Odyssey", "City", "Element", "Crosstour", "Passport"],
    "Hummer": ["H1", "H2", "H3"],
    "Hyundai": ["Grand i10", "Accent", "Elantra", "Tucson", "Santa Fe", "Creta", "Sonata", "ix35", "Verna", "Staria"],
    "Infiniti": ["QX50", "QX60", "QX70", "QX80", "Q50", "Q60", "G35", "G37"],
    "Isuzu": ["D-Max", "ELF", "Rodeo", "Amigo"],
    "Jaguar": ["F-Pace", "XE", "XF", "X-Type", "S-Type"],
    "Jeep": ["Grand Cherokee", "Wrangler", "Compass", "Cherokee", "Renegade", "Liberty", "Commander", "Patriot", "Gladiator"],
    "Jetour": ["X70", "X70 Plus", "Dashing", "X90 Plus"],
    "Kia": ["Rio", "Forte", "Sportage", "Seltos", "Soul", "Optima", "Sorento", "Sedona", "K3", "Sonet", "Niro"],
    "Land Rover": ["Defender", "Discovery", "Range Rover Evoque", "Freelander", "LR3", "LR4"],
    "Lexus": ["RX", "NX", "IS", "ES", "UX", "LX"],
    "Lincoln": ["Navigator", "MKZ", "Aviator", "MKX", "MKS", "Town Car", "Corsair", "Nautilus"],
    "Mazda": ["Mazda 2", "Mazda 3", "Mazda 6", "CX-3", "CX-5", "CX-9", "MX-5", "CX-30", "CX-50", "CX-7", "Protege"],
    "Mercedes-Benz": ["Clase C", "Clase E", "Clase A", "Clase B", "GLA", "GLC", "GLE", "ML", "Sprinter"],
    "MG": ["MG5", "HS", "ZS", "RX5", "GT", "ONE", "MG3"],
    "Mini": ["Cooper", "Countryman", "Clubman", "Paceman"],
    "Mitsubishi": ["L200", "Outlander", "Mirage", "Mirage G4", "Montero Sport", "Eclipse", "Lancer", "Endeavor", "Galant"],
    "Nissan": ["Tsuru", "Tsuru I", "Tsuru II", "Tsuru III", "Versa", "Sentra", "March", "Frontier", "X-Trail", "Kicks", "Altima", "Maxima", "Tiida", "Platina", "Aprio", "Tsubame", "Hikari", "Pathfinder", "Murano", "Armada", "Urvan", "Estaquitas", "D21", "NP300", "Note"],
    "Omoda": ["O5", "O5 GT", "C5"],
    "Peugeot": ["206", "207", "208", "301", "307", "308", "2008", "3008", "Partner", "Rifter", "Manager", "406"],
    "Pontiac": ["Matiz", "G3", "G6", "Grand Am", "Sunfire", "Grand Prix", "Torrent", "Solstice", "Aztek"],
    "Porsche": ["Cayenne", "Macan", "911", "Boxster", "Panamera", "Cayman"],
    "Ram": ["700", "1500", "2500", "4000", "ProMaster", "Charger"],
    "Renault": ["Clio", "Platina", "Kwid", "Duster", "Logan", "Stepway", "Captur", "Megane", "Fluence", "Koleos", "Scenic", "Kangoo", "Oroch"],
    "Scion": ["xB", "tC", "xA"],
    "Seat": ["Ibiza", "Leon", "Ateca", "Arona", "Toledo", "Cordoba", "Altea", "Freetrack", "Tarraco"],
    "Smart": ["Fortwo", "Forfour", "Roadster"],
    "Subaru": ["Impreza", "XV", "Forester", "Outback", "WRX", "BRZ"],
    "Suzuki": ["Swift", "Vitara", "Grand Vitara", "Ignis", "Ertiga", "Jimny", "Ciaz", "S-Cross", "Aerio", "SX4"],
    "Toyota": ["Hilux", "Yaris", "Corolla", "RAV4", "Camry", "Tacoma", "Tundra", "Prius", "Sienna", "Avanza", "Hiace", "Matrix", "Corona", "Celica"],
    "Volkswagen": ["Pointer", "Gol", "Vento", "Polo", "Jetta", "Jetta A3", "Jetta A4", "Clasico", "Bora", "Beetle", "Passat", "Derby", "Corsar", "Combi", "Vocho", "Sedan", "Golf", "Golf A4", "Tiguan", "Taos", "Saveiro", "Amarok", "Crafter", "Transporter", "CrossFox", "Lupo", "Sharan", "Eurovan"],
    "Volvo": ["XC40", "XC60", "XC90", "S40", "S60", "C30", "V40"]
}

def seed_database(db: Session):
    admin = db.query(models.Usuario).filter(models.Usuario.usuario == "admin").first()
    if not admin:
        new_admin = models.Usuario(
            nombre="Administrador General",
            usuario="admin",
            contrasena_hash=obtener_password_hash("AdminCorp2026*"),
            rol=models.RolEnum.Administrador,
            telefono_celular="+529990000000"
        )
        db.add(new_admin)
        db.commit()
