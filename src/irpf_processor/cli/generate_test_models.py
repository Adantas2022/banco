#!/usr/bin/env python
"""CLI para gerar modelos de teste IRPF de diferentes anos e perfis.

Uso:
    python -m irpf_processor.cli.generate_test_models
    python -m irpf_processor.cli.generate_test_models --years 2025 2024 2023
    python -m irpf_processor.cli.generate_test_models --profiles wealthy rural_large
    python -m irpf_processor.cli.generate_test_models --random 50
    python -m irpf_processor.cli.generate_test_models --all
    python -m irpf_processor.cli.generate_test_models --test
"""

import argparse
import sys
from pathlib import Path

from irpf_processor.infrastructure.receita_federal.test_pdf_generator import (
    TestPDFGenerator,
    AdvancedTestGenerator,
)


PROFILE_DESCRIPTIONS = {
    "minimal": "📉 Mínimo - 1-3 bens, 1 fonte de renda",
    "simple": "📊 Simples - 3-8 bens, até 2 fontes",
    "average": "📈 Médio - 5-15 bens, até 3 fontes",
    "wealthy": "💰 Rico - 15-40 bens, múltiplas fontes",
    "ultra_rich": "💎 Ultra-rico - 40-100 bens, atividade rural",
    "rural_small": "🌱 Rural Pequeno - Produtor com até 10 bens",
    "rural_large": "🌾 Rural Grande - Fazendeiro com 10-30 bens",
    "retired": "👴 Aposentado - Patrimônio acumulado",
    "investor": "📊 Investidor - Muitos ativos financeiros",
}


def print_header():
    print()
    print("=" * 70)
    print("  📄 IRPF Processor - Gerador Avançado de Modelos de Teste")
    print("  🧪 PDFs sintéticos com alta variabilidade")
    print("=" * 70)
    print()


def cmd_generate(args):
    print_header()
    
    generator = TestPDFGenerator()
    
    years = args.years if args.years else ["2025", "2024", "2023"]
    profiles = args.profiles if args.profiles else ["random"]
    
    if args.all:
        profiles = list(AdvancedTestGenerator.PROFILES.keys())
    
    print(f"📅 Anos: {', '.join(years)}")
    print(f"👤 Perfis: {', '.join(profiles)}")
    print()
    
    if profiles == ["random"]:
        print("🎲 Modo aleatório - perfis serão escolhidos randomicamente")
        print()
    
    print("🔄 Gerando modelos de teste...")
    print()
    
    files = []
    for year in years:
        for profile in profiles:
            for _ in range(args.count):
                filepath = generator.generate_pdf(year, profile)
                files.append(filepath)
    
    by_year = {}
    for f in files:
        year = f.parent.name
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(f)
    
    for year in sorted(by_year.keys(), reverse=True):
        print(f"📁 {year}/")
        for f in by_year[year]:
            size_kb = f.stat().st_size / 1024 if f.exists() else 0
            
            parts = f.stem.split("_")
            profile = parts[3] if len(parts) >= 4 else "unknown"
            
            icon = "🌾" if "rural" in profile else "💼"
            if profile == "wealthy" or profile == "ultra_rich":
                icon = "💰"
            elif profile == "investor":
                icon = "📊"
            elif profile == "retired":
                icon = "👴"
            
            print(f"   {icon} {f.name} ({size_kb:.1f} KB)")
    
    print()
    print("-" * 70)
    
    stats = generator.get_stats()
    print(f"📊 Estatísticas:")
    print(f"   📁 Total de arquivos: {stats['total_files']}")
    print(f"   💾 Tamanho total: {stats['total_size_mb']:.2f} MB")
    print(f"   📅 Anos: {', '.join(sorted(stats['years'], reverse=True))}")
    print()
    print(f"   👤 Por perfil:")
    for profile, count in sorted(stats['profiles'].items()):
        desc = PROFILE_DESCRIPTIONS.get(profile, profile)
        print(f"      {desc}: {count}")
    
    print()
    print(f"📂 Diretório: {generator.output_dir}")
    print()


def cmd_random(args):
    print_header()
    
    generator = TestPDFGenerator()
    
    years = args.years if args.years else ["2025", "2024", "2023"]
    count = args.random
    
    print(f"🎲 Gerando {count} declarações aleatórias...")
    print(f"📅 Anos: {', '.join(years)}")
    print()
    
    files = generator.generate_random_batch(years, total_count=count)
    
    by_year = {}
    by_profile = {}
    for f in files:
        year = f.parent.name
        if year not in by_year:
            by_year[year] = 0
        by_year[year] += 1
        
        parts = f.stem.split("_")
        profile = parts[3] if len(parts) >= 4 else "unknown"
        if profile not in by_profile:
            by_profile[profile] = 0
        by_profile[profile] += 1
    
    print("📊 Distribuição gerada:")
    print()
    print("   📅 Por ano:")
    for year in sorted(by_year.keys(), reverse=True):
        print(f"      {year}: {by_year[year]} arquivos")
    
    print()
    print("   👤 Por perfil:")
    for profile in sorted(by_profile.keys()):
        desc = PROFILE_DESCRIPTIONS.get(profile, profile)
        print(f"      {desc}: {by_profile[profile]}")
    
    stats = generator.get_stats()
    print()
    print(f"📁 Total de arquivos: {stats['total_files']}")
    print(f"💾 Tamanho total: {stats['total_size_mb']:.2f} MB")
    print(f"📂 Diretório: {generator.output_dir}")
    print()


def cmd_list(args):
    print_header()
    
    generator = TestPDFGenerator()
    generated = generator.list_generated()
    
    if not generated:
        print("📋 Nenhum modelo de teste gerado ainda.")
        print()
        print("   Execute: python -m irpf_processor.cli.generate_test_models")
        print()
        return
    
    print("📋 Modelos de teste disponíveis:")
    print()
    
    for year in sorted(generated.keys(), reverse=True):
        files = generated[year]
        print(f"📁 {year}/ ({len(files)} arquivos)")
        
        by_profile = {}
        for f in files:
            parts = f.stem.split("_")
            profile = parts[3] if len(parts) >= 4 else "other"
            if profile not in by_profile:
                by_profile[profile] = []
            by_profile[profile].append(f)
        
        for profile in sorted(by_profile.keys()):
            count = len(by_profile[profile])
            desc = PROFILE_DESCRIPTIONS.get(profile, profile)
            print(f"   {desc}: {count}")
        print()
    
    stats = generator.get_stats()
    print("-" * 70)
    print(f"📊 Total: {stats['total_files']} arquivos, {stats['total_size_mb']:.2f} MB")
    print(f"📂 Diretório: {generator.output_dir}")
    print()


def cmd_test_parser(args):
    print_header()
    
    from irpf_processor.infrastructure.extraction import IRPFParser
    
    generator = TestPDFGenerator()
    generated = generator.list_generated()
    
    if not generated:
        print("⚠️  Nenhum modelo de teste encontrado. Gerando...")
        print()
        files = generator.generate_random_batch(["2025", "2024", "2023"], total_count=9)
        generated = generator.list_generated()
    
    parser = IRPFParser()
    
    print(f"🔧 Parser com templates: {parser.available_versions}")
    print()
    print("🧪 Testando parser com modelos gerados:")
    print()
    
    results = []
    tested = 0
    max_tests = args.max_tests if hasattr(args, 'max_tests') else 20
    
    for year in sorted(generated.keys(), reverse=True):
        files = generated[year]
        for f in files:
            if tested >= max_tests:
                break
            
            tested += 1
            parts = f.stem.split("_")
            profile = parts[3] if len(parts) >= 4 else "unknown"
            
            try:
                if f.suffix == '.txt':
                    text = f.read_text(encoding='utf-8')
                    detected = parser._template_registry.detect_version(text)
                else:
                    result = parser.parse(f)
                    detected = parser.detected_version
                
                status = "✅" if detected == year else "⚠️"
                match = detected == year
                
                print(f"{status} {f.name}")
                print(f"   Esperado: {year} | Detectado: {detected} | Perfil: {profile}")
                
                if f.suffix == '.pdf':
                    print(f"   Confiança: {result.confidence:.1%} | Bens: {len(result.assets_declaration.get('items', [])) if result.assets_declaration else 0}")
                
                results.append((year, detected, match, profile))
                
            except Exception as e:
                print(f"❌ {f.name}")
                print(f"   Erro: {str(e)[:60]}")
                results.append((year, None, False, profile))
            
            print()
        
        if tested >= max_tests:
            break
    
    passed = sum(1 for _, _, ok, _ in results if ok)
    total = len(results)
    
    print("=" * 70)
    print(f"📊 Resultado: {passed}/{total} corretos ({100*passed/total:.1f}%)")
    
    by_profile = {}
    for year, detected, ok, profile in results:
        if profile not in by_profile:
            by_profile[profile] = {"total": 0, "passed": 0}
        by_profile[profile]["total"] += 1
        if ok:
            by_profile[profile]["passed"] += 1
    
    print()
    print("📊 Por perfil:")
    for profile in sorted(by_profile.keys()):
        data = by_profile[profile]
        pct = 100 * data["passed"] / data["total"] if data["total"] > 0 else 0
        status = "✅" if pct == 100 else "⚠️" if pct >= 50 else "❌"
        print(f"   {status} {profile}: {data['passed']}/{data['total']} ({pct:.0f}%)")
    
    print()


def cmd_profiles(args):
    print_header()
    
    print("👤 Perfis de declaração disponíveis:")
    print()
    
    for profile, desc in PROFILE_DESCRIPTIONS.items():
        config = AdvancedTestGenerator.PROFILES[profile]
        print(f"   {desc}")
        print(f"      Bens: {config['assets'][0]}-{config['assets'][1]}")
        print(f"      Fontes de renda: {config['income_sources'][0]}-{config['income_sources'][1]}")
        print(f"      Rendimentos isentos: {config['exempt'][0]}-{config['exempt'][1]}")
        print(f"      Atividade rural: {'Sim' if config['rural'] else 'Não'}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Gera modelos de teste IRPF para diferentes anos e perfis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s                            # Gera 1 modelo aleatório por ano
  %(prog)s --years 2025 2024          # Anos específicos
  %(prog)s --profiles wealthy rural   # Perfis específicos
  %(prog)s --all                      # Todos os perfis
  %(prog)s --random 50                # 50 modelos aleatórios
  %(prog)s --count 3                  # 3 modelos por combinação
  %(prog)s --list                     # Lista modelos gerados
  %(prog)s --test                     # Testa parser
  %(prog)s --profiles-help            # Lista perfis disponíveis
        """
    )
    
    parser.add_argument(
        "--years", "-y",
        nargs="+",
        help="Anos para gerar modelos (ex: 2025 2024 2023)",
    )
    
    parser.add_argument(
        "--profiles", "-p",
        nargs="+",
        help="Perfis específicos (ex: wealthy rural_large investor)",
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Gera para todos os perfis",
    )
    
    parser.add_argument(
        "--random", "-r",
        type=int,
        metavar="N",
        help="Gera N modelos com anos e perfis aleatórios",
    )
    
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=1,
        help="Quantidade de modelos por combinação ano/perfil (default: 1)",
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Lista modelos gerados",
    )
    
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Testa o parser com os modelos gerados",
    )
    
    parser.add_argument(
        "--max-tests",
        type=int,
        default=20,
        help="Máximo de arquivos para testar (default: 20)",
    )
    
    parser.add_argument(
        "--profiles-help",
        action="store_true",
        help="Mostra descrição dos perfis disponíveis",
    )
    
    args = parser.parse_args()
    
    try:
        if args.profiles_help:
            cmd_profiles(args)
        elif args.list:
            cmd_list(args)
        elif args.test:
            cmd_test_parser(args)
        elif args.random:
            cmd_random(args)
        else:
            cmd_generate(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
