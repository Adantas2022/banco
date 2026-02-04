"""Gerador de PDFs de teste para diferentes versões do IRPF.

Gera declarações sintéticas com alta variabilidade para testar o parser:
- Diferentes anos (2021-2025)
- Variações de patrimônio (pequeno a grande)
- Com/sem atividade rural
- Com/sem dependentes
- Múltiplas fontes de renda
- Edge cases e cenários extremos
"""

import random
import string
from dataclasses import dataclass, field
from datetime import datetime, date
from io import BytesIO
from pathlib import Path
from typing import Optional
from decimal import Decimal

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


FIRST_NAMES_M = [
    "JOSE", "JOAO", "ANTONIO", "FRANCISCO", "CARLOS", "PAULO", "PEDRO", "LUCAS",
    "LUIZ", "MARCOS", "GABRIEL", "RAFAEL", "DANIEL", "MARCELO", "BRUNO", "EDUARDO",
    "FELIPE", "RODRIGO", "ANDRE", "GUSTAVO", "SERGIO", "RICARDO", "FERNANDO", "JORGE",
    "ROBERTO", "FABIO", "LEONARDO", "WAGNER", "THIAGO", "LEANDRO", "MATHEUS", "VINICIUS",
]

FIRST_NAMES_F = [
    "MARIA", "ANA", "FRANCISCA", "ADRIANA", "JULIANA", "MARCIA", "FERNANDA", "PATRICIA",
    "ALINE", "SANDRA", "CAMILA", "AMANDA", "BRUNA", "JESSICA", "LETICIA", "JULIA",
    "LUCIANA", "VANESSA", "CARLA", "SIMONE", "RENATA", "CRISTIANE", "RAFAELA", "HELENA",
    "LARISSA", "BEATRIZ", "GABRIELA", "CAROLINA", "NATALIA", "TATIANA", "PRISCILA", "MONICA",
]

LAST_NAMES = [
    "SILVA", "SANTOS", "OLIVEIRA", "SOUZA", "RODRIGUES", "FERREIRA", "ALVES", "PEREIRA",
    "LIMA", "GOMES", "COSTA", "RIBEIRO", "MARTINS", "CARVALHO", "ALMEIDA", "LOPES",
    "SOARES", "FERNANDES", "VIEIRA", "BARBOSA", "ROCHA", "DIAS", "NASCIMENTO", "ANDRADE",
    "MOREIRA", "NUNES", "MARQUES", "MACHADO", "MENDES", "FREITAS", "CARDOSO", "RAMOS",
    "GONÇALVES", "SANTANA", "TEIXEIRA", "MOURA", "CORREIA", "ARAUJO", "PINTO", "CAMPOS",
]

CITIES = [
    ("SAO PAULO", "SP", "01310-100"),
    ("RIO DE JANEIRO", "RJ", "20040-020"),
    ("BELO HORIZONTE", "MG", "30130-000"),
    ("BRASILIA", "DF", "70040-010"),
    ("SALVADOR", "BA", "40020-000"),
    ("FORTALEZA", "CE", "60060-440"),
    ("CURITIBA", "PR", "80010-000"),
    ("RECIFE", "PE", "50030-230"),
    ("PORTO ALEGRE", "RS", "90010-150"),
    ("MANAUS", "AM", "69005-140"),
    ("GOIANIA", "GO", "74003-010"),
    ("BELEM", "PA", "66010-020"),
    ("GUARULHOS", "SP", "07011-000"),
    ("CAMPINAS", "SP", "13010-111"),
    ("SAO LUIS", "MA", "65010-440"),
    ("MACEIO", "AL", "57020-460"),
    ("NATAL", "RN", "59010-000"),
    ("CAMPO GRANDE", "MS", "79002-000"),
    ("JOAO PESSOA", "PB", "58010-000"),
    ("TERESINA", "PI", "64001-280"),
    ("RIBEIRAO PRETO", "SP", "14010-000"),
    ("UBERLANDIA", "MG", "38400-100"),
    ("SOROCABA", "SP", "18010-000"),
    ("CUIABA", "MT", "78005-100"),
]

STREETS = [
    "RUA DAS FLORES", "AVENIDA BRASIL", "RUA SAO PAULO", "AVENIDA PAULISTA",
    "RUA QUINZE DE NOVEMBRO", "AVENIDA ATLANTICA", "RUA AUGUSTA", "AVENIDA COPACABANA",
    "RUA DO COMERCIO", "AVENIDA CENTRAL", "RUA DA LIBERDADE", "AVENIDA INDEPENDENCIA",
    "RUA SETE DE SETEMBRO", "AVENIDA RIO BRANCO", "RUA TIRADENTES", "AVENIDA GETULIO VARGAS",
    "RUA MARECHAL DEODORO", "AVENIDA PRESIDENTE VARGAS", "RUA DOM PEDRO", "AVENIDA SANTOS DUMONT",
]

NEIGHBORHOODS = [
    "CENTRO", "JARDIM AMERICA", "VILA MARIANA", "PINHEIROS", "MOEMA", "ITAIM BIBI",
    "COPACABANA", "IPANEMA", "LEBLON", "BOTAFOGO", "LAPA", "TIJUCA", "SAVASSI",
    "FUNCIONARIOS", "LOURDES", "ASA SUL", "ASA NORTE", "LAGO SUL", "BOA VIAGEM",
    "MEIRELES", "ALDEOTA", "BATEL", "AGUA VERDE", "CENTRO HISTORICO", "MOINHOS DE VENTO",
]

OCCUPATIONS = [
    ("11", "PROPRIETARIO OU SOCIO DE EMPRESA"),
    ("12", "DIRETOR DE EMPRESA"),
    ("13", "TRABALHADOR AUTONOMO"),
    ("21", "SERVIDOR PUBLICO FEDERAL"),
    ("22", "SERVIDOR PUBLICO ESTADUAL"),
    ("23", "SERVIDOR PUBLICO MUNICIPAL"),
    ("24", "SERVIDOR PUBLICO - OUTRO"),
    ("31", "EMPREGADO DE EMPRESA PRIVADA"),
    ("41", "MEDICO"),
    ("42", "ADVOGADO"),
    ("43", "ENGENHEIRO"),
    ("44", "CONTADOR"),
    ("45", "PROFESSOR"),
    ("51", "PRODUTOR RURAL"),
    ("52", "PECUARISTA"),
    ("61", "APOSENTADO"),
    ("62", "PENSIONISTA"),
    ("91", "OUTROS"),
]

COMPANIES = [
    ("PETROBRAS S.A.", "33.000.167/0001-01"),
    ("BANCO DO BRASIL S.A.", "00.000.000/0001-91"),
    ("VALE S.A.", "33.592.510/0001-54"),
    ("ITAU UNIBANCO S.A.", "60.701.190/0001-04"),
    ("BRADESCO S.A.", "60.746.948/0001-12"),
    ("AMBEV S.A.", "07.526.557/0001-00"),
    ("JBS S.A.", "02.916.265/0001-60"),
    ("MAGAZINE LUIZA S.A.", "47.960.950/0001-21"),
    ("LOCALIZA RENT A CAR S.A.", "16.670.085/0001-55"),
    ("WEG S.A.", "84.429.695/0001-11"),
    ("SUZANO S.A.", "16.404.287/0001-55"),
    ("TELEFONICA BRASIL S.A.", "02.558.157/0001-62"),
    ("ENERGISA S.A.", "00.864.214/0001-06"),
    ("COPEL S.A.", "76.483.817/0001-20"),
    ("CEMIG S.A.", "17.155.730/0001-64"),
    ("SABESP S.A.", "43.776.517/0001-80"),
    ("CCR S.A.", "02.846.056/0001-97"),
    ("GERDAU S.A.", "33.611.500/0001-19"),
    ("USIMINAS S.A.", "60.894.730/0001-05"),
    ("CSN S.A.", "33.042.730/0001-04"),
]

BANKS = [
    ("BANCO DO BRASIL S.A.", "00.000.000/0001-91"),
    ("CAIXA ECONOMICA FEDERAL", "00.360.305/0001-04"),
    ("ITAU UNIBANCO S.A.", "60.701.190/0001-04"),
    ("BRADESCO S.A.", "60.746.948/0001-12"),
    ("SANTANDER BRASIL S.A.", "90.400.888/0001-42"),
    ("BTG PACTUAL S.A.", "30.306.294/0001-45"),
    ("SAFRA S.A.", "58.160.789/0001-28"),
    ("NUBANK S.A.", "18.236.120/0001-58"),
    ("INTER S.A.", "00.416.968/0001-01"),
    ("XP INVESTIMENTOS", "02.332.886/0001-04"),
]

ASSET_TYPES = [
    ("01", "01", "Prédio residencial"),
    ("01", "02", "Prédio comercial"),
    ("01", "03", "Galpão"),
    ("01", "11", "Apartamento"),
    ("01", "12", "Casa"),
    ("01", "13", "Terreno"),
    ("01", "14", "Imóvel rural"),
    ("01", "15", "Sala ou conjunto"),
    ("01", "16", "Construção"),
    ("01", "17", "Benfeitorias"),
    ("01", "99", "Outros bens imóveis"),
    ("02", "01", "Veículo automotor terrestre"),
    ("02", "02", "Aeronave"),
    ("02", "03", "Embarcação"),
    ("02", "99", "Outros bens móveis"),
    ("03", "01", "Participação societária"),
    ("04", "01", "Aplicação de renda fixa"),
    ("04", "02", "Aplicação de renda variável"),
    ("04", "03", "Fundo de investimento"),
    ("04", "04", "Ações"),
    ("04", "05", "Poupança"),
    ("04", "06", "Depósito bancário"),
    ("05", "01", "Crédito decorrente de empréstimo"),
    ("05", "02", "Crédito decorrente de alienação"),
    ("06", "01", "Depósito em conta corrente no exterior"),
    ("07", "01", "Joia, quadro, objeto de arte"),
    ("07", "02", "Coleção"),
    ("99", "99", "Outros bens e direitos"),
]

VEHICLE_BRANDS = [
    "TOYOTA COROLLA", "HONDA CIVIC", "VOLKSWAGEN GOL", "CHEVROLET ONIX",
    "FIAT ARGO", "HYUNDAI HB20", "JEEP COMPASS", "FORD RANGER",
    "BMW 320I", "MERCEDES C200", "AUDI A3", "VOLVO XC60",
    "LAND ROVER DISCOVERY", "PORSCHE CAYENNE", "FERRARI 488", "LAMBORGHINI HURACAN",
]

RURAL_PROPERTIES = [
    "FAZENDA BOA ESPERANCA", "SITIO SAO JOSE", "CHACARA NOSSA SENHORA",
    "FAZENDA SANTA MARIA", "ESTANCIA BOM JESUS", "FAZENDA CACHOEIRA",
    "SITIO RECANTO VERDE", "FAZENDA SOL NASCENTE", "CHACARA PRIMAVERA",
    "FAZENDA AGUA CLARA", "SITIO PEDRA GRANDE", "FAZENDA MONTE ALEGRE",
]

EXEMPT_INCOME_CODES = [
    ("01", "Bolsas de estudo e pesquisa"),
    ("03", "Capital das apólices de seguro"),
    ("04", "Indenizações por rescisão de contrato de trabalho"),
    ("05", "Lucro na alienação de bem de pequeno valor"),
    ("06", "Lucro na alienação de único imóvel"),
    ("07", "Transferências patrimoniais - doações"),
    ("08", "Transferências patrimoniais - heranças"),
    ("09", "Lucros e dividendos recebidos"),
    ("10", "Parcela isenta de proventos de aposentadoria"),
    ("11", "Pensão, proventos de aposentadoria - moléstia grave"),
    ("12", "Rendimento de caderneta de poupança"),
    ("13", "Rendimentos de letras hipotecárias"),
    ("14", "Rendimentos de certificados de recebíveis"),
    ("15", "75% dos rendimentos do trabalho assalariado - exterior"),
    ("26", "Outros"),
]

EXCLUSIVE_INCOME_CODES = [
    ("01", "Décimo terceiro salário"),
    ("02", "Rendimentos de aplicações financeiras"),
    ("03", "Ganhos de capital na alienação de bens"),
    ("04", "Ganhos líquidos em operações de renda variável"),
    ("05", "Prêmios de loterias e sorteios"),
    ("06", "Rendimentos de aplicações em fundos"),
    ("07", "Juros sobre capital próprio"),
    ("08", "Participação nos lucros ou resultados"),
    ("12", "Outros"),
]


def generate_valid_cpf() -> str:
    def calc_digit(cpf_slice: list[int], factors: list[int]) -> int:
        total = sum(d * f for d, f in zip(cpf_slice, factors))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder
    
    base = [random.randint(0, 9) for _ in range(9)]
    first_digit = calc_digit(base, [10, 9, 8, 7, 6, 5, 4, 3, 2])
    base.append(first_digit)
    second_digit = calc_digit(base, [11, 10, 9, 8, 7, 6, 5, 4, 3, 2])
    base.append(second_digit)
    
    cpf_str = "".join(map(str, base))
    return f"{cpf_str[:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:]}"


def generate_valid_cnpj() -> str:
    def calc_digit(cnpj_slice: list[int], factors: list[int]) -> int:
        total = sum(d * f for d, f in zip(cnpj_slice, factors))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder
    
    base = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    first_digit = calc_digit(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    base.append(first_digit)
    second_digit = calc_digit(base, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    base.append(second_digit)
    
    cnpj_str = "".join(map(str, base))
    return f"{cnpj_str[:2]}.{cnpj_str[2:5]}.{cnpj_str[5:8]}/{cnpj_str[8:12]}-{cnpj_str[12:]}"


def generate_random_name() -> str:
    gender = random.choice(["M", "F"])
    first_names = FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F
    
    name_parts = [random.choice(first_names)]
    
    if random.random() > 0.3:
        name_parts.append(random.choice(LAST_NAMES))
    
    name_parts.append(random.choice(LAST_NAMES))
    
    return " ".join(name_parts)


def generate_random_address() -> dict:
    city, state, cep_base = random.choice(CITIES)
    
    return {
        "street": random.choice(STREETS),
        "number": str(random.randint(1, 9999)),
        "complement": random.choice(["", "APTO " + str(random.randint(1, 500)), "SALA " + str(random.randint(1, 100)), "BLOCO " + random.choice(["A", "B", "C"])]),
        "neighborhood": random.choice(NEIGHBORHOODS),
        "city": city,
        "state": state,
        "cep": cep_base,
    }


def format_currency(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class AssetItem:
    group_code: str
    item_code: str
    description: str
    country_code: str = "105"
    country_name: str = "BRASIL"
    previous_value: float = 0.0
    current_value: float = 0.0
    additional_info: str = ""


@dataclass
class IncomeItem:
    payer_name: str
    payer_cnpj: str
    gross_income: float
    social_security: float = 0.0
    tax_withheld: float = 0.0
    thirteenth: float = 0.0
    thirteenth_tax: float = 0.0


@dataclass
class ExemptIncomeItem:
    code: str
    description: str
    beneficiary: str
    beneficiary_cpf: str
    payer_name: str
    payer_cnpj: str
    value: float


@dataclass
class RuralProperty:
    code: int
    participation: float
    condition: int
    name: str
    location: str
    area: float
    cib: str


@dataclass 
class RuralMonthData:
    month: str
    revenue: float
    expenses: float


@dataclass
class TestDeclaration:
    exercise_year: str
    calendar_year: str
    cpf: str
    name: str
    occupation_code: str
    occupation_name: str
    address: dict
    
    assets: list[AssetItem] = field(default_factory=list)
    income_pj: list[IncomeItem] = field(default_factory=list)
    exempt_income: list[ExemptIncomeItem] = field(default_factory=list)
    exclusive_income: list[ExemptIncomeItem] = field(default_factory=list)
    
    has_rural: bool = False
    rural_properties: list[RuralProperty] = field(default_factory=list)
    rural_months: list[RuralMonthData] = field(default_factory=list)
    
    dependents: list[dict] = field(default_factory=list)
    
    @property
    def total_assets_previous(self) -> float:
        return sum(a.previous_value for a in self.assets)
    
    @property
    def total_assets_current(self) -> float:
        return sum(a.current_value for a in self.assets)
    
    @property
    def total_income(self) -> float:
        return sum(i.gross_income for i in self.income_pj)
    
    @property
    def total_exempt(self) -> float:
        return sum(i.value for i in self.exempt_income)
    
    @property
    def total_exclusive(self) -> float:
        return sum(i.value for i in self.exclusive_income)
    
    @property
    def total_rural_revenue(self) -> float:
        return sum(m.revenue for m in self.rural_months)
    
    @property
    def total_rural_expenses(self) -> float:
        return sum(m.expenses for m in self.rural_months)


class AdvancedTestGenerator:
    """Gerador avançado de declarações de teste."""
    
    PROFILES = {
        "minimal": {"assets": (1, 3), "income_sources": (1, 1), "exempt": (0, 2), "rural": False},
        "simple": {"assets": (3, 8), "income_sources": (1, 2), "exempt": (1, 4), "rural": False},
        "average": {"assets": (5, 15), "income_sources": (1, 3), "exempt": (2, 6), "rural": False},
        "wealthy": {"assets": (15, 40), "income_sources": (2, 5), "exempt": (5, 15), "rural": False},
        "ultra_rich": {"assets": (40, 100), "income_sources": (5, 10), "exempt": (10, 30), "rural": True},
        "rural_small": {"assets": (3, 10), "income_sources": (1, 2), "exempt": (1, 3), "rural": True},
        "rural_large": {"assets": (10, 30), "income_sources": (2, 4), "exempt": (3, 8), "rural": True},
        "retired": {"assets": (5, 20), "income_sources": (0, 1), "exempt": (2, 5), "rural": False},
        "investor": {"assets": (20, 50), "income_sources": (1, 2), "exempt": (10, 25), "rural": False},
    }
    
    def __init__(self):
        pass
    
    def generate(
        self, 
        exercise_year: str,
        profile: str = "random",
    ) -> TestDeclaration:
        if profile == "random":
            profile = random.choice(list(self.PROFILES.keys()))
        
        config = self.PROFILES.get(profile, self.PROFILES["average"])
        calendar_year = str(int(exercise_year) - 1)
        
        occupation = random.choice(OCCUPATIONS)
        if profile == "retired":
            occupation = ("61", "APOSENTADO")
        elif profile in ["rural_small", "rural_large"]:
            occupation = random.choice([("51", "PRODUTOR RURAL"), ("52", "PECUARISTA")])
        
        decl = TestDeclaration(
            exercise_year=exercise_year,
            calendar_year=calendar_year,
            cpf=generate_valid_cpf(),
            name=generate_random_name(),
            occupation_code=occupation[0],
            occupation_name=occupation[1],
            address=generate_random_address(),
        )
        
        self._generate_assets(decl, config, profile)
        self._generate_income(decl, config, profile)
        self._generate_exempt_income(decl, config)
        self._generate_exclusive_income(decl, config)
        
        if config["rural"] or random.random() > 0.8:
            decl.has_rural = True
            self._generate_rural_activity(decl, profile)
        
        if random.random() > 0.6:
            self._generate_dependents(decl)
        
        return decl
    
    def _generate_assets(self, decl: TestDeclaration, config: dict, profile: str):
        min_assets, max_assets = config["assets"]
        num_assets = random.randint(min_assets, max_assets)
        
        base_value = {
            "minimal": 50000,
            "simple": 200000,
            "average": 500000,
            "wealthy": 2000000,
            "ultra_rich": 10000000,
            "rural_small": 300000,
            "rural_large": 3000000,
            "retired": 800000,
            "investor": 5000000,
        }.get(profile, 500000)
        
        has_home = random.random() > 0.2
        if has_home:
            home_type = random.choice([("01", "11", "Apartamento"), ("01", "12", "Casa")])
            home_value = random.uniform(base_value * 0.3, base_value * 0.8)
            decl.assets.append(AssetItem(
                group_code=home_type[0],
                item_code=home_type[1],
                description=f"{home_type[2].upper()} - {decl.address['street']}, {decl.address['number']}",
                previous_value=home_value * random.uniform(0.9, 1.0),
                current_value=home_value,
                additional_info=f"Matrícula: {random.randint(10000, 99999)} - Cartório: {random.randint(1, 20)}º Ofício",
            ))
            num_assets -= 1
        
        has_vehicle = random.random() > 0.3
        if has_vehicle and num_assets > 0:
            vehicle = random.choice(VEHICLE_BRANDS)
            year = int(decl.calendar_year) - random.randint(0, 5)
            vehicle_value = random.uniform(30000, 300000)
            if "BMW" in vehicle or "MERCEDES" in vehicle or "AUDI" in vehicle:
                vehicle_value = random.uniform(150000, 500000)
            if "FERRARI" in vehicle or "LAMBORGHINI" in vehicle or "PORSCHE" in vehicle:
                vehicle_value = random.uniform(500000, 3000000)
            
            decl.assets.append(AssetItem(
                group_code="02",
                item_code="01",
                description=f"{vehicle} {year}",
                previous_value=vehicle_value * 1.1,
                current_value=vehicle_value,
                additional_info=f"RENAVAM: {random.randint(10000000000, 99999999999)}",
            ))
            num_assets -= 1
        
        for _ in range(num_assets):
            asset_type = random.choice(ASSET_TYPES)
            
            if asset_type[0] == "04":
                bank = random.choice(BANKS)
                value = random.uniform(10000, base_value * 0.3)
                description = f"{asset_type[2].upper()} - {bank[0]}"
                additional = f"CNPJ: {bank[1]} - Agência: {random.randint(1, 9999)} - Conta: {random.randint(10000, 99999)}"
            elif asset_type[0] == "03":
                company = random.choice(COMPANIES)
                value = random.uniform(50000, base_value * 0.5)
                description = f"QUOTAS DE CAPITAL - {company[0]}"
                additional = f"CNPJ: {company[1]} - {random.randint(1, 100)}% do capital"
            else:
                value = random.uniform(5000, base_value * 0.2)
                description = f"{asset_type[2].upper()}"
                additional = ""
            
            growth = random.uniform(-0.1, 0.15)
            
            decl.assets.append(AssetItem(
                group_code=asset_type[0],
                item_code=asset_type[1],
                description=description,
                previous_value=value * (1 - growth),
                current_value=value,
                additional_info=additional,
            ))
    
    def _generate_income(self, decl: TestDeclaration, config: dict, profile: str):
        min_sources, max_sources = config["income_sources"]
        num_sources = random.randint(min_sources, max_sources)
        
        if num_sources == 0 and profile == "retired":
            return
        
        base_income = {
            "minimal": 30000,
            "simple": 80000,
            "average": 150000,
            "wealthy": 500000,
            "ultra_rich": 2000000,
            "rural_small": 100000,
            "rural_large": 400000,
            "retired": 60000,
            "investor": 300000,
        }.get(profile, 150000)
        
        for i in range(num_sources):
            company = random.choice(COMPANIES)
            income = random.uniform(base_income * 0.3, base_income) / num_sources
            
            ss_rate = random.uniform(0.08, 0.14)
            tax_rate = random.uniform(0.0, 0.275)
            
            decl.income_pj.append(IncomeItem(
                payer_name=company[0],
                payer_cnpj=company[1],
                gross_income=income,
                social_security=income * ss_rate,
                tax_withheld=income * tax_rate,
                thirteenth=income / 12 if random.random() > 0.2 else 0,
                thirteenth_tax=income / 12 * 0.15 if random.random() > 0.2 else 0,
            ))
    
    def _generate_exempt_income(self, decl: TestDeclaration, config: dict):
        min_exempt, max_exempt = config["exempt"]
        num_exempt = random.randint(min_exempt, max_exempt)
        
        if random.random() > 0.4:
            code = "09"
            desc = "Lucros e dividendos recebidos"
            company = random.choice(COMPANIES)
            value = random.uniform(10000, 200000)
            
            decl.exempt_income.append(ExemptIncomeItem(
                code=code,
                description=desc,
                beneficiary="Titular",
                beneficiary_cpf=decl.cpf,
                payer_name=company[0],
                payer_cnpj=company[1],
                value=value,
            ))
            num_exempt -= 1
        
        for _ in range(num_exempt):
            code, desc = random.choice(EXEMPT_INCOME_CODES)
            company = random.choice(COMPANIES + BANKS)
            value = random.uniform(1000, 50000)
            
            decl.exempt_income.append(ExemptIncomeItem(
                code=code,
                description=desc,
                beneficiary="Titular",
                beneficiary_cpf=decl.cpf,
                payer_name=company[0],
                payer_cnpj=company[1],
                value=value,
            ))
    
    def _generate_exclusive_income(self, decl: TestDeclaration, config: dict):
        num_exclusive = random.randint(1, 5)
        
        for _ in range(num_exclusive):
            code, desc = random.choice(EXCLUSIVE_INCOME_CODES)
            company = random.choice(COMPANIES + BANKS)
            value = random.uniform(500, 30000)
            
            decl.exclusive_income.append(ExemptIncomeItem(
                code=code,
                description=desc,
                beneficiary="Titular",
                beneficiary_cpf=decl.cpf,
                payer_name=company[0],
                payer_cnpj=company[1],
                value=value,
            ))
    
    def _generate_rural_activity(self, decl: TestDeclaration, profile: str):
        num_properties = 1 if profile == "rural_small" else random.randint(1, 3)
        
        for i in range(num_properties):
            city, state, _ = random.choice(CITIES)
            prop_name = random.choice(RURAL_PROPERTIES)
            
            decl.rural_properties.append(RuralProperty(
                code=i + 1,
                participation=100.0 / num_properties,
                condition=1,
                name=prop_name,
                location=f"{city}/{state}",
                area=random.uniform(50, 5000),
                cib="".join([str(random.randint(0, 9)) for _ in range(10)]),
            ))
        
        months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        
        base_revenue = 50000 if profile == "rural_small" else 200000
        
        for month in months:
            seasonality = 1.0 + random.uniform(-0.3, 0.5)
            revenue = base_revenue * seasonality * random.uniform(0.8, 1.2)
            expenses = revenue * random.uniform(0.4, 0.7)
            
            decl.rural_months.append(RuralMonthData(
                month=month,
                revenue=revenue,
                expenses=expenses,
            ))
    
    def _generate_dependents(self, decl: TestDeclaration):
        num_dependents = random.randint(1, 4)
        
        for i in range(num_dependents):
            dep_type = random.choice(["filho", "cônjuge", "pai/mãe"])
            
            if dep_type == "filho":
                birth_year = int(decl.calendar_year) - random.randint(1, 21)
            elif dep_type == "cônjuge":
                birth_year = int(decl.calendar_year) - random.randint(25, 60)
            else:
                birth_year = int(decl.calendar_year) - random.randint(50, 85)
            
            decl.dependents.append({
                "name": generate_random_name(),
                "cpf": generate_valid_cpf(),
                "birth_date": f"01/01/{birth_year}",
                "type": dep_type,
            })


class TestPDFGenerator:
    """Gera PDFs de teste para diferentes versões do IRPF."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "data" / "modelos"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.generator = AdvancedTestGenerator()
    
    def _declaration_to_text(self, decl: TestDeclaration) -> str:
        lines = []
        
        lines.append("=" * 80)
        lines.append("MINISTÉRIO DA FAZENDA")
        lines.append("SECRETARIA ESPECIAL DA RECEITA FEDERAL DO BRASIL")
        lines.append("DECLARAÇÃO DE AJUSTE ANUAL")
        lines.append("")
        lines.append(f"EXERCÍCIO {decl.exercise_year} ANO-CALENDÁRIO {decl.calendar_year}")
        lines.append("=" * 80)
        lines.append("")
        
        lines.append("-" * 80)
        lines.append("IDENTIFICAÇÃO DO CONTRIBUINTE")
        lines.append("-" * 80)
        lines.append(f"CPF: {decl.cpf}")
        lines.append(f"Nome: {decl.name}")
        lines.append(f"Natureza da Ocupação: {decl.occupation_code} - {decl.occupation_name}")
        lines.append(f"Ocupação Principal: {decl.occupation_name}")
        lines.append("")
        lines.append(f"Endereço: {decl.address['street']}, {decl.address['number']}")
        if decl.address['complement']:
            lines.append(f"Complemento: {decl.address['complement']}")
        lines.append(f"Bairro: {decl.address['neighborhood']}")
        lines.append(f"Município: {decl.address['city']}")
        lines.append(f"UF: {decl.address['state']}")
        lines.append(f"CEP: {decl.address['cep']}")
        lines.append("")
        
        if decl.dependents:
            lines.append("-" * 80)
            lines.append("RELAÇÃO DE DEPENDENTES")
            lines.append("-" * 80)
            for i, dep in enumerate(decl.dependents, 1):
                lines.append(f"{i}. {dep['name']}")
                lines.append(f"   CPF: {dep['cpf']} - Nascimento: {dep['birth_date']}")
            lines.append("")
        
        lines.append("-" * 80)
        lines.append("DECLARAÇÃO DE BENS E DIREITOS")
        lines.append("-" * 80)
        lines.append(f"{'Cód':<6} {'Discriminação':<40} {'31/12/' + str(int(decl.calendar_year)-1):>15} {'31/12/' + decl.calendar_year:>15}")
        lines.append("-" * 80)
        
        for i, asset in enumerate(decl.assets, 1):
            code = f"{asset.group_code}.{asset.item_code}"
            desc = asset.description[:38]
            prev = format_currency(asset.previous_value)
            curr = format_currency(asset.current_value)
            lines.append(f"{code:<6} {desc:<40} {prev:>15} {curr:>15}")
            if asset.additional_info:
                lines.append(f"       {asset.additional_info[:70]}")
        
        lines.append("-" * 80)
        lines.append(f"{'TOTAL':<46} {format_currency(decl.total_assets_previous):>15} {format_currency(decl.total_assets_current):>15}")
        lines.append("")
        
        if decl.income_pj:
            lines.append("-" * 80)
            lines.append("RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR")
            lines.append("-" * 80)
            lines.append(f"{'Fonte Pagadora':<35} {'Rendimentos':>15} {'INSS':>12} {'IRRF':>12}")
            lines.append("-" * 80)
            
            for inc in decl.income_pj:
                name = inc.payer_name[:33]
                lines.append(f"{name:<35} {format_currency(inc.gross_income):>15} {format_currency(inc.social_security):>12} {format_currency(inc.tax_withheld):>12}")
                lines.append(f"CNPJ: {inc.payer_cnpj}")
                if inc.thirteenth > 0:
                    lines.append(f"13º Salário: {format_currency(inc.thirteenth)} - IRRF 13º: {format_currency(inc.thirteenth_tax)}")
            
            total_income = sum(i.gross_income for i in decl.income_pj)
            total_ss = sum(i.social_security for i in decl.income_pj)
            total_tax = sum(i.tax_withheld for i in decl.income_pj)
            lines.append("-" * 80)
            lines.append(f"{'TOTAL':<35} {format_currency(total_income):>15} {format_currency(total_ss):>12} {format_currency(total_tax):>12}")
            lines.append("")
        
        if decl.exempt_income:
            lines.append("-" * 80)
            lines.append("RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS")
            lines.append("-" * 80)
            
            by_code = {}
            for inc in decl.exempt_income:
                if inc.code not in by_code:
                    by_code[inc.code] = {"desc": inc.description, "items": [], "total": 0}
                by_code[inc.code]["items"].append(inc)
                by_code[inc.code]["total"] += inc.value
            
            for code in sorted(by_code.keys()):
                data = by_code[code]
                lines.append(f"{code}. {data['desc']} {format_currency(data['total']):>50}")
                for item in data["items"]:
                    lines.append(f"   {item.beneficiary:<10} {item.beneficiary_cpf:<18} {item.payer_cnpj:<20} {item.payer_name[:20]:<20} {format_currency(item.value):>15}")
            
            lines.append("-" * 80)
            lines.append(f"TOTAL DE RENDIMENTOS ISENTOS {format_currency(decl.total_exempt):>50}")
            lines.append("")
        
        if decl.exclusive_income:
            lines.append("-" * 80)
            lines.append("RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA")
            lines.append("-" * 80)
            
            for inc in decl.exclusive_income:
                lines.append(f"{inc.code}. {inc.description:<50} {format_currency(inc.value):>15}")
            
            lines.append("-" * 80)
            lines.append(f"TOTAL {format_currency(decl.total_exclusive):>72}")
            lines.append("")
        
        if decl.has_rural:
            lines.append("-" * 80)
            lines.append("ATIVIDADE RURAL - BRASIL")
            lines.append("-" * 80)
            lines.append("")
            lines.append("DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO")
            lines.append("")
            
            for prop in decl.rural_properties:
                lines.append(f"Código: {prop.code}")
                lines.append(f"Participação: {prop.participation:.2f}%")
                lines.append(f"Condição de Exploração: {prop.condition} - Proprietário")
                lines.append(f"Nome e Localização: {prop.name} - {prop.location}")
                lines.append(f"Área: {prop.area:.2f} ha")
                lines.append(f"CIB/NIRF: {prop.cib}")
                lines.append("")
            
            lines.append("RECEITAS E DESPESAS")
            lines.append("")
            lines.append(f"{'Mês':<15} {'Receita Bruta':>20} {'Despesas':>20}")
            lines.append("-" * 55)
            
            for month_data in decl.rural_months:
                lines.append(f"{month_data.month:<15} {format_currency(month_data.revenue):>20} {format_currency(month_data.expenses):>20}")
            
            lines.append("-" * 55)
            lines.append(f"{'TOTAL':<15} {format_currency(decl.total_rural_revenue):>20} {format_currency(decl.total_rural_expenses):>20}")
            lines.append("")
            
            result = decl.total_rural_revenue - decl.total_rural_expenses
            lines.append(f"RESULTADO DA ATIVIDADE RURAL: {format_currency(result)}")
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("RESUMO DA DECLARAÇÃO")
        lines.append("=" * 80)
        lines.append(f"Total de Bens e Direitos: R$ {format_currency(decl.total_assets_current)}")
        lines.append(f"Rendimentos Tributáveis:  R$ {format_currency(decl.total_income)}")
        lines.append(f"Rendimentos Isentos:      R$ {format_currency(decl.total_exempt)}")
        lines.append(f"Tributação Exclusiva:     R$ {format_currency(decl.total_exclusive)}")
        if decl.has_rural:
            lines.append(f"Receita Rural:            R$ {format_currency(decl.total_rural_revenue)}")
        lines.append("")
        lines.append(f"Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        lines.append("")
        lines.append("=" * 80)
        lines.append("DOCUMENTO GERADO PARA FINS DE TESTE - NÃO POSSUI VALOR LEGAL")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_pdf(
        self, 
        exercise_year: str,
        profile: str = "random",
    ) -> Path:
        decl = self.generator.generate(exercise_year, profile)
        text = self._declaration_to_text(decl)
        
        year_dir = self.output_dir / exercise_year
        year_dir.mkdir(exist_ok=True)
        
        cpf_clean = decl.cpf.replace(".", "").replace("-", "")
        
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import cm
            from reportlab.lib.enums import TA_LEFT
            
            filename = f"irpf_{exercise_year}_{cpf_clean}_{profile}.pdf"
            filepath = year_dir / filename
            
            doc = SimpleDocTemplate(
                str(filepath),
                pagesize=A4,
                rightMargin=1.5*cm,
                leftMargin=1.5*cm,
                topMargin=1.5*cm,
                bottomMargin=1.5*cm,
            )
            
            styles = getSampleStyleSheet()
            code_style = ParagraphStyle(
                'Code',
                parent=styles['Normal'],
                fontName='Courier',
                fontSize=7,
                leading=9,
                alignment=TA_LEFT,
            )
            
            story = []
            for line in text.split('\n'):
                if line.strip():
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, code_style))
                else:
                    story.append(Spacer(1, 4))
            
            doc.build(story)
            
        except ImportError:
            filename = f"irpf_{exercise_year}_{cpf_clean}_{profile}.txt"
            filepath = year_dir / filename
            filepath.write_text(text, encoding='utf-8')
        
        logger.info(
            "Test declaration generated",
            year=exercise_year,
            profile=profile,
            file=filename,
            cpf=decl.cpf,
            assets=len(decl.assets),
            income_sources=len(decl.income_pj),
            has_rural=decl.has_rural,
        )
        
        return filepath
    
    def generate_batch(
        self,
        years: list[str],
        profiles: Optional[list[str]] = None,
        count_per_combination: int = 1,
    ) -> list[Path]:
        if profiles is None:
            profiles = list(AdvancedTestGenerator.PROFILES.keys())
        
        files = []
        
        for year in years:
            for profile in profiles:
                for _ in range(count_per_combination):
                    filepath = self.generate_pdf(year, profile)
                    files.append(filepath)
        
        return files
    
    def generate_random_batch(
        self,
        years: list[str],
        total_count: int = 20,
    ) -> list[Path]:
        files = []
        profiles = list(AdvancedTestGenerator.PROFILES.keys())
        
        for _ in range(total_count):
            year = random.choice(years)
            profile = random.choice(profiles)
            filepath = self.generate_pdf(year, profile)
            files.append(filepath)
        
        return files
    
    def list_generated(self) -> dict[str, list[Path]]:
        result = {}
        
        for year_dir in self.output_dir.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                files = list(year_dir.glob("irpf_*.*"))
                if files:
                    result[year_dir.name] = sorted(files)
        
        return result
    
    def get_stats(self) -> dict:
        generated = self.list_generated()
        
        total_files = sum(len(files) for files in generated.values())
        total_size = sum(
            f.stat().st_size 
            for files in generated.values() 
            for f in files
        )
        
        profiles_count = {}
        for files in generated.values():
            for f in files:
                parts = f.stem.split("_")
                if len(parts) >= 4:
                    profile = parts[3]
                    profiles_count[profile] = profiles_count.get(profile, 0) + 1
        
        return {
            "total_files": total_files,
            "total_size_mb": total_size / (1024 * 1024),
            "years": list(generated.keys()),
            "profiles": profiles_count,
        }
