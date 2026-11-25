"""Datos ficticios de la semilla."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    title: str
    salary: str
    start: str


@dataclass(frozen=True)
class Person:
    first_name: str
    last_name: str
    email: str
    department: str
    positions: tuple[Position, ...]  # del más antiguo al actual
    manager: str | None = None  # email del jefe; debe aparecer antes en la lista


# Departamento -> email de su encargado.
DEPARTMENTS = {
    "Dirección": "elena.vargas@example.com",
    "Tecnología": "marcos.ibanez@example.com",
    "Recursos Humanos": "lucia.ferrer@example.com",
    "Finanzas": "andres.molina@example.com",
    "Ventas": "paula.rivas@example.com",
}

# 20 empleados, cada uno con un puesto actual distinto. El orden importa: primero los jefes.
PEOPLE = (
    Person(
        "Elena",
        "Vargas",
        "elena.vargas@example.com",
        "Dirección",
        (
            Position("Dirección Comercial", "5200.00", "2014-02-03"),
            Position("Dirección General", "8500.00", "2019-01-01"),
        ),
    ),
    Person(
        "Marcos",
        "Ibáñez",
        "marcos.ibanez@example.com",
        "Tecnología",
        (
            Position("Líder de Desarrollo", "4200.00", "2015-05-11"),
            Position("Dirección de Tecnología", "6800.00", "2020-03-01"),
        ),
        "elena.vargas@example.com",
    ),
    Person(
        "Lucía",
        "Ferrer",
        "lucia.ferrer@example.com",
        "Recursos Humanos",
        (
            Position("Selección de Personal", "2400.00", "2016-09-05"),
            Position("Dirección de Recursos Humanos", "5600.00", "2021-07-01"),
        ),
        "elena.vargas@example.com",
    ),
    Person(
        "Andrés",
        "Molina",
        "andres.molina@example.com",
        "Finanzas",
        (
            Position("Contabilidad", "2300.00", "2013-01-14"),
            Position("Análisis Financiero", "3100.00", "2016-04-01"),
            Position("Dirección Financiera", "6200.00", "2020-01-01"),
        ),
        "elena.vargas@example.com",
    ),
    Person(
        "Paula",
        "Rivas",
        "paula.rivas@example.com",
        "Ventas",
        (
            Position("Gerencia de Ventas", "3900.00", "2017-03-20"),
            Position("Dirección Comercial", "6000.00", "2019-01-01"),
        ),
        "elena.vargas@example.com",
    ),
    Person(
        "Diego",
        "Campos",
        "diego.campos@example.com",
        "Tecnología",
        (
            Position("Desarrollo Backend Senior", "3400.00", "2018-06-04"),
            Position("Líder de Desarrollo", "4600.00", "2020-03-01"),
        ),
        "marcos.ibanez@example.com",
    ),
    Person(
        "Sofía",
        "Navarro",
        "sofia.navarro@example.com",
        "Tecnología",
        (
            Position("Ingeniería DevOps", "3300.00", "2018-10-15"),
            Position("Líder de Infraestructura", "4500.00", "2022-02-01"),
        ),
        "marcos.ibanez@example.com",
    ),
    Person(
        "Javier",
        "Ortega",
        "javier.ortega@example.com",
        "Tecnología",
        (
            Position("Desarrollo Backend Junior", "1800.00", "2019-04-08"),
            Position("Desarrollo Backend Senior", "3500.00", "2022-05-01"),
        ),
        "diego.campos@example.com",
    ),
    Person(
        "Carmen",
        "Lozano",
        "carmen.lozano@example.com",
        "Tecnología",
        (Position("Desarrollo Frontend Senior", "3400.00", "2020-11-02"),),
        "diego.campos@example.com",
    ),
    Person(
        "Mateo",
        "Reyes",
        "mateo.reyes@example.com",
        "Tecnología",
        (Position("Desarrollo Backend Junior", "1950.00", "2024-01-15"),),
        "javier.ortega@example.com",
    ),
    Person(
        "Valeria",
        "Cruz",
        "valeria.cruz@example.com",
        "Tecnología",
        (Position("Diseño UX/UI", "2700.00", "2021-08-23"),),
        "diego.campos@example.com",
    ),
    Person(
        "Raúl",
        "Peña",
        "raul.pena@example.com",
        "Tecnología",
        (
            Position("Soporte Técnico", "1600.00", "2019-02-18"),
            Position("Control de Calidad", "2400.00", "2022-09-01"),
        ),
        "diego.campos@example.com",
    ),
    Person(
        "Irene",
        "Soto",
        "irene.soto@example.com",
        "Tecnología",
        (Position("Ingeniería DevOps", "3350.00", "2022-02-14"),),
        "sofia.navarro@example.com",
    ),
    Person(
        "Hugo",
        "Medina",
        "hugo.medina@example.com",
        "Tecnología",
        (Position("Soporte Técnico", "1700.00", "2023-03-06"),),
        "sofia.navarro@example.com",
    ),
    Person(
        "Natalia",
        "Gil",
        "natalia.gil@example.com",
        "Recursos Humanos",
        (Position("Selección de Personal", "2350.00", "2021-09-13"),),
        "lucia.ferrer@example.com",
    ),
    Person(
        "Óscar",
        "Delgado",
        "oscar.delgado@example.com",
        "Recursos Humanos",
        (
            Position("Contabilidad", "2100.00", "2018-01-22"),
            Position("Nóminas", "2500.00", "2021-07-01"),
        ),
        "lucia.ferrer@example.com",
    ),
    Person(
        "Beatriz",
        "Santos",
        "beatriz.santos@example.com",
        "Finanzas",
        (Position("Contabilidad", "2250.00", "2020-05-18"),),
        "andres.molina@example.com",
    ),
    Person(
        "Tomás",
        "Aguilar",
        "tomas.aguilar@example.com",
        "Finanzas",
        (
            Position("Nóminas", "2200.00", "2019-07-29"),
            Position("Análisis Financiero", "3050.00", "2021-07-01"),
        ),
        "andres.molina@example.com",
    ),
    Person(
        "Clara",
        "Vidal",
        "clara.vidal@example.com",
        "Ventas",
        (
            Position("Asesoría Comercial", "1900.00", "2017-11-06"),
            Position("Gerencia de Ventas", "3800.00", "2019-02-01"),
        ),
        "paula.rivas@example.com",
    ),
    Person(
        "Iván",
        "Romero",
        "ivan.romero@example.com",
        "Ventas",
        (Position("Asesoría Comercial", "1850.00", "2023-10-02"),),
        "clara.vidal@example.com",
    ),
)
