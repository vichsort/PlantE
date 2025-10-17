import click
from flask import current_app
from .services.plant_id_service import PlantIdService
from .services.gemini_service import GeminiService
from .utils.base64_utils import encode_image_to_base64

def register_commands(app):
    """Registra os comandos de linha de comando na aplicação Flask."""

    @app.cli.command("analyze")
    @click.argument("image_path")
    def analyze_plant_command(image_path):
        """
        Executa a análise completa de uma planta a partir de uma imagem.
        Uso: flask analyze "caminho/para/sua/imagem.jpg"
        """
        click.echo(f"🌿 Analisando a imagem: {image_path}\n")

        plant_service = PlantIdService(api_key=current_app.config['PLANT_ID_API_KEY'])
        gemini_service = GeminiService(api_key=current_app.config['GEMINI_API_KEY'])
        
        try:
            image_b64 = encode_image_to_base64(image_path)
        except FileNotFoundError:
            click.secho(f"❌ Erro: Arquivo de imagem não encontrado em '{image_path}'", fg='red')
            return
        
        plant_name = None

        # --- 1. Identificação da Planta ---
        try:
            identification = plant_service.identify_plant(image_b64)
            best_match = identification['result']['classification']['suggestions'][0]
            plant_name = best_match['name']
            probability = best_match['probability']
            
            click.echo("🔍 Identificação Concluída:")
            click.echo(f"   - Nome: {plant_name} (Probabilidade: {probability:.2%})")
            click.echo("-" * 30)

        except (KeyError, IndexError, Exception) as e:
            click.secho(f"❌ Erro na identificação: {e}", fg='red')
            return

        # --- 2. Avaliação de Saúde ---
        try:
            health_assessment = plant_service.assess_health(image_b64)
            diseases = health_assessment.get('result', {}).get('disease', {}).get('suggestions', [])
            
            click.echo("🩺 Avaliação de Saúde:")
            
            # Primeiro, procuramos por doenças de alta probabilidade
            high_prob_disease = None
            for disease in diseases:
                if disease['probability'] > 0.2:
                    high_prob_disease = disease
                    break # Encontramos uma, não precisa continuar
            
            if high_prob_disease and plant_name:
                # --- PLANTA DOENTE (COM CERTEZA) ---
                disease_name = high_prob_disease['name']
                disease_prob = high_prob_disease['probability']
                click.echo(f"   - Doença com alta probabilidade detectada: {disease_name} ({disease_prob:.2%})")
                
                click.secho("   - Consultando o Gemini para um plano de tratamento...", fg='yellow')
                treatment_plan = gemini_service.get_disease_treatment_plan(plant_name, disease_name)
                
                click.echo("\n--- Plano de Tratamento (via Gemini) ---")
                click.echo(f"   Doença: {treatment_plan.disease_name}")
                click.echo(f"   Sintomas: {', '.join(treatment_plan.symptoms)}")
                click.echo("   Tratamento:")
                for step in treatment_plan.treatment_plan:
                    click.echo(f"     - {step}")
                click.echo(f"   Tempo de Recuperação: {treatment_plan.recovery_time}")
                click.echo("----------------------------------------\n")

            else:
                # --- PLANTA SAUDÁVEL OU COM DOENÇAS DE BAIXA PROBABILIDADE ---
                if not diseases:
                    click.secho("   - Nenhuma doença detectada. A planta parece saudável!", fg='green')
                else:
                    click.secho("   - Detectadas possíveis doenças de baixa probabilidade (ignorando para detalhes):", fg='yellow')
                    for disease in diseases:
                         click.echo(f"     - {disease['name']} (Probabilidade: {disease['probability']:.2%})")

                if plant_name:
                    click.secho("\n🧠 Buscando informações detalhadas com o Gemini...", fg='cyan')
                    
                    plant_details = gemini_service.get_details_about_plant(plant_name)
                    click.echo("\n--- Detalhes da Planta (via Gemini) ---")
                    click.echo(f"   Nomes Populares: {', '.join(plant_details.popular_name)}")
                    click.echo(f"   Descrição: {plant_details.description}")
                    click.echo(f"   Taxonomia: Família {plant_details.taxonomy.familia}, Gênero {plant_details.taxonomy.genus}")
                    click.echo(f"   É comestível? {'Sim' if plant_details.is_edible else 'Não'}")
                    click.echo(f"   Rega: {plant_details.water}")
                    click.echo(f"   Estação de Plantio: {plant_details.season}")
                    click.echo(f"   Luz Solar: {plant_details.sunlight}")
                    click.echo(f"   Solo Ideal: {plant_details.soil}")
                    click.echo("----------------------------------------")

                    nutritional_details = gemini_service.get_nutritional_details(plant_name)
                    click.echo("\n--- Informações Nutricionais e Medicinais (via Gemini) ---")
                    click.echo("   Chá:")
                    for step in nutritional_details.tea:
                        click.echo(f"     - {step}")

                    click.echo(f"   Receita Sugerida: {nutritional_details.food.name}")
                    click.echo(f"   Ingredientes: {', '.join(nutritional_details.food.ingredients)}")
                    click.echo(f"   Uso Medicinal: {nutritional_details.heal.how_to_use}")
                    click.echo(f"   Benefícios: {', '.join(nutritional_details.heal.benefits)}")
                    click.echo(f"   Uso como Tempero: {nutritional_details.seasoning}")
                    click.echo("----------------------------------------")

            click.echo("\n" + "-" * 30)
        except Exception as e:
            click.secho(f"\n❌ Erro na avaliação ou consulta ao Gemini: {e}", fg='red')