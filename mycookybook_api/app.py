"""
Flask API pour scraper des recettes et parser les ingrédients
VERSION AMÉLIORÉE - Extraction robuste du cookTime depuis schema.org JSON-LD
"""

from flask import Flask, request, jsonify
from recipe_scrapers import scrape_html
import re
import unicodedata
import json
import extruct
from w3lib.html import get_base_url
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from bs4 import BeautifulSoup
import requests

# ============================================================================
# NOTE SUR LES DONNÉES DE MESURE
#
# Ce script charge désormais un fichier JSON comportant toutes les unités
# disponibles dans plusieurs langues. Ces données proviennent d'une base
# multilingue (voir units_multilingual_complete.json). Chaque entrée définit
# un code standard et une liste d'alias par langue. Cela permet de générer
# dynamiquement des patterns pour détecter les unités dans les ingrédients.
# Les patterns statiques existants sont conservés pour les abréviations
# classiques (ml, g, tbsp, etc.) mais les alias supplémentaires améliorent
# considérablement la prise en charge des pluriels et des variantes.


# ============================================================================
# UTILITAIRES POUR EXTRACTION SCHEMA.ORG
# ============================================================================

def parse_iso_duration(duration_str: str) -> Optional[int]:
    """
    Parse une durée ISO 8601 (ex: PT1H30M) et retourne les minutes
    
    Args:
        duration_str: String au format ISO 8601 (PT1H30M, PT45M, PT2H, etc.)
    
    Returns:
        Nombre de minutes ou None si impossible à parser
    """
    if not duration_str or not isinstance(duration_str, str):
        return None
    
    try:
        # Nettoyer et normaliser la chaîne
        duration_str = duration_str.strip().upper()
        
        # Pattern pour extraire heures, minutes et secondes
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            
            # Convertir tout en minutes (arrondir les secondes)
            total_minutes = hours * 60 + minutes + (seconds // 60)
            return total_minutes if total_minutes > 0 else None
        
        return None
    except Exception as e:
        print(f"Erreur parsing durée ISO: {e}")
        return None


def extract_json_ld(html_content: str) -> List[Dict]:
    """
    Extrait tous les blocs JSON-LD du HTML
    
    Args:
        html_content: Contenu HTML de la page
    
    Returns:
        Liste des objets JSON-LD trouvés
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    
    json_ld_objects = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            # Gérer les cas où data est une liste ou un objet
            if isinstance(data, list):
                json_ld_objects.extend(data)
            else:
                json_ld_objects.append(data)
        except json.JSONDecodeError as e:
            print(f"Erreur décodage JSON-LD: {e}")
            continue
    
    return json_ld_objects


def find_recipe_schema(json_ld_objects: List[Dict]) -> Optional[Dict]:
    """
    Trouve l'objet Recipe dans les données JSON-LD
    
    Args:
        json_ld_objects: Liste des objets JSON-LD
    
    Returns:
        L'objet Recipe ou None si non trouvé
    """
    for obj in json_ld_objects:
        # Vérifier @type directement
        obj_type = obj.get('@type', '')
        
        if isinstance(obj_type, str) and 'Recipe' in obj_type:
            return obj
        
        # Vérifier @type comme liste
        if isinstance(obj_type, list) and any('Recipe' in str(t) for t in obj_type):
            return obj
        
        # Vérifier @graph (certains sites utilisent ce format)
        if '@graph' in obj and isinstance(obj['@graph'], list):
            for item in obj['@graph']:
                item_type = item.get('@type', '')
                if isinstance(item_type, str) and 'Recipe' in item_type:
                    return item
                if isinstance(item_type, list) and any('Recipe' in str(t) for t in item_type):
                    return item
    
    return None


def extract_time_from_schema(recipe_schema: Dict, time_field: str) -> Optional[int]:
    """
    Extrait un champ de temps du schema et le convertit en minutes
    
    Args:
        recipe_schema: Objet Recipe du schema.org
        time_field: Nom du champ (cookTime, prepTime, totalTime)
    
    Returns:
        Durée en minutes ou None
    """
    if not recipe_schema:
        return None
    
    time_value = recipe_schema.get(time_field)
    
    # Cas 1: Valeur string directe (format ISO)
    if isinstance(time_value, str):
        return parse_iso_duration(time_value)
    
    # Cas 2: Objet avec @value
    if isinstance(time_value, dict) and '@value' in time_value:
        return parse_iso_duration(time_value['@value'])
    
    # Cas 3: Objet avec 'value'
    if isinstance(time_value, dict) and 'value' in time_value:
        return parse_iso_duration(time_value['value'])
    
    return None


def scrape_with_enhanced_schema(url: str) -> Tuple[Any, Dict]:
    """
    Scrape une recette avec extraction améliorée des données schema.org
    
    Args:
        url: URL de la recette
    
    Returns:
        Tuple (scraper object, enhanced_data dict)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
    }
    
    # UN SEUL téléchargement
    response = requests.get(url, timeout=20, headers=headers)
    response.raise_for_status()
    html_content = response.text

    # Passer le HTML déjà téléchargé au scraper (pas de 2e GET)
    scraper = scrape_html(html_content, org_url=url, supported_only=False)

    enhanced_data = {}

    try:
        # Réutiliser le HTML déjà téléchargé — pas de 2e requête HTTP
        json_ld_objects = extract_json_ld(html_content)
        recipe_schema = find_recipe_schema(json_ld_objects)
        
        if recipe_schema:
            print(f"✓ Schema.org Recipe trouvé")
            
            # Extraire les temps depuis le schema.org
            cook_time = extract_time_from_schema(recipe_schema, 'cookTime')
            prep_time = extract_time_from_schema(recipe_schema, 'prepTime')
            total_time = extract_time_from_schema(recipe_schema, 'totalTime')
            
            if cook_time is not None:
                enhanced_data['cook_time'] = cook_time
                print(f"  - cookTime: {cook_time} min")
            
            if prep_time is not None:
                enhanced_data['prep_time'] = prep_time
                print(f"  - prepTime: {prep_time} min")
            
            if total_time is not None:
                enhanced_data['total_time'] = total_time
                print(f"  - totalTime: {total_time} min")
            
            # Autres champs du schema.org
            if 'recipeYield' in recipe_schema:
                enhanced_data['yields'] = recipe_schema['recipeYield']
            
            if 'recipeCategory' in recipe_schema:
                enhanced_data['category'] = recipe_schema['recipeCategory']
            
            if 'recipeCuisine' in recipe_schema:
                enhanced_data['cuisine'] = recipe_schema['recipeCuisine']
            
            if 'keywords' in recipe_schema:
                keywords = recipe_schema['keywords']
                if isinstance(keywords, list):
                    enhanced_data['keywords'] = keywords
                elif isinstance(keywords, str):
                    enhanced_data['keywords'] = [k.strip() for k in keywords.split(',')]
            
            # Nutrition
            if 'nutrition' in recipe_schema:
                nutrition = recipe_schema['nutrition']
                if isinstance(nutrition, dict):
                    nutrients = {}
                    nutrition_fields = {
                        'calories': 'calories',
                        'fatContent': 'fat',
                        'saturatedFatContent': 'saturatedFat',
                        'transFatContent': 'transFat',
                        'cholesterolContent': 'cholesterol',
                        'sodiumContent': 'sodium',
                        'carbohydrateContent': 'carbohydrates',
                        'fiberContent': 'fiber',
                        'sugarContent': 'sugar',
                        'proteinContent': 'protein',
                    }
                    for schema_key, output_key in nutrition_fields.items():
                        if schema_key in nutrition and nutrition[schema_key]:
                            nutrients[output_key] = nutrition[schema_key]
                    
                    if nutrients:
                        enhanced_data['nutrients'] = nutrients
            
            # Ratings
            if 'aggregateRating' in recipe_schema:
                rating = recipe_schema['aggregateRating']
                if isinstance(rating, dict):
                    if 'ratingValue' in rating:
                        try:
                            enhanced_data['ratings'] = float(rating['ratingValue'])
                        except (ValueError, TypeError):
                            pass
                    if 'ratingCount' in rating:
                        try:
                            enhanced_data['ratings_count'] = int(rating['ratingCount'])
                        except (ValueError, TypeError):
                            pass
            
            # Auteur
            if 'author' in recipe_schema:
                author = recipe_schema['author']
                if isinstance(author, dict) and 'name' in author:
                    enhanced_data['author'] = author['name']
                elif isinstance(author, str):
                    enhanced_data['author'] = author
                elif isinstance(author, list) and len(author) > 0:
                    if isinstance(author[0], dict) and 'name' in author[0]:
                        enhanced_data['author'] = author[0]['name']
                    elif isinstance(author[0], str):
                        enhanced_data['author'] = author[0]
        else:
            print("✗ Aucun schema.org Recipe trouvé dans la page")
            
    except Exception as e:
        print(f"Erreur lors de l'extraction schema.org: {e}")
    
    return scraper, enhanced_data


# ============================================================================
# PARSEUR D'INGRÉDIENTS MULTILINGUE
# ============================================================================

class Language(Enum):
    """Langues supportées"""
    FR = "fr"
    EN = "en"
    ES = "es"
    DE = "de"


@dataclass
class ParsedIngredient:
    """Résultat du parsing d'un ingrédient"""
    ingredient: str
    quantity: Optional[float] = None
    unit: str = ""
    note: str = ""
    raw_text: str = ""


class MultilingualIngredientParser:
    """
    Parseur d'ingrédients multilingue pour recettes de cuisine.
    Supporte: français, anglais, espagnol, allemand
    """
    
    def __init__(self, units: Optional[List[Dict[str, Any]]] = None, default_language: Language = Language.FR):
        # Charge la liste d'unités passée en paramètre. Si aucune unité n'est
        # spécifiée, self.units restera vide et seuls les patterns statiques
        # seront utilisés. Passer la liste complète issue du JSON permet de
        # construire dynamiquement les patterns de détection.
        self.units: List[Dict[str, Any]] = units or []
        self.default_language = default_language
        # Mapping simple nom -> code (hérité de l'implémentation initiale)
        self.unit_map = self.build_unit_map()
        # Construction des patterns de langue statiques (tbsp, tsp, etc.)
        self._init_language_patterns()
        # Construction des patterns dynamiques basés sur les alias du JSON
        self.unit_alias_patterns: Dict[Language, List[Tuple[re.Pattern, str]]] = self.build_unit_alias_patterns()

        # Table de normalisation des codes d'unité. Certaines unités décrites
        # dans les données multilingues utilisent des codes spécifiques (c_a_c,
        # c_a_s, cas, cac, cs, etc.) pour représenter les abréviations de
        # cuillères à café et cuillères à soupe. Afin de converger vers des
        # unités standards (tsp, tbsp), on normalise ces codes via ce
        # dictionnaire. Les clés en minuscules seront converties à leurs
        # équivalents standards.
        self.unit_code_normalization = {
            'c_a_c': 'tsp',
            'cac': 'tsp',
            'cc': 'tsp',
            'c_a_s': 'tbsp',
            'cas': 'tbsp',
            'cs': 'tbsp',
            'pincee': 'pinch',
            'pincees': 'pinch',
        }

        # Certaines expressions fixes ne doivent pas être analysées comme des unités.
        # Par exemple "bouquet garni" est une préparation aromatique et non une unité.
        # On définit une liste par langue de ces expressions à éviter.
        self.skip_unit_phrases: Dict[Language, List[str]] = {
            Language.FR: ['bouquet garni'],
            Language.EN: ['bouquet garni'],
            Language.ES: ['bouquet garni'],
            Language.DE: ['bouquet garni'],
        }

        # Table de localisation des codes d'unité standard → terme dans chaque langue.
        # Les unités universelles (g, kg, ml, cl, l, oz, lb) sont identiques dans
        # toutes les langues et ne figurent pas ici (le fallback renvoie le code tel quel).
        self.unit_localized_labels: Dict[Language, Dict[str, str]] = {
            Language.FR: {
                'tbsp': 'c. à soupe',
                'tsp': 'c. à café',
                'cup': 'tasse',
                'glass': 'verre',
                'jar': 'pot',
                'can': 'boîte',
                'packet': 'sachet',
                'package': 'paquet',
                'pinch': 'pincée',
                'sprig': 'branche',
                'clove': 'gousse',
                'leaf': 'feuille',
                'slice': 'tranche',
                'bunch': 'botte',
                'piece': 'morceau',
            },
            Language.EN: {
                'tbsp': 'tbsp',
                'tsp': 'tsp',
                'cup': 'cup',
                'glass': 'glass',
                'jar': 'jar',
                'can': 'can',
                'packet': 'packet',
                'package': 'package',
                'pinch': 'pinch',
                'sprig': 'sprig',
                'clove': 'clove',
                'leaf': 'leaf',
                'slice': 'slice',
                'bunch': 'bunch',
                'piece': 'piece',
            },
            Language.ES: {
                'tbsp': 'cda.',
                'tsp': 'cdta.',
                'cup': 'taza',
                'jar': 'tarro',
                'can': 'lata',
                'packet': 'sobre',
                'pinch': 'pizca',
                'sprig': 'rama',
                'clove': 'diente',
                'leaf': 'hoja',
                'slice': 'rodaja',
                'bunch': 'manojo',
                'piece': 'trozo',
            },
            Language.DE: {
                'tbsp': 'EL',
                'tsp': 'TL',
                'cup': 'Tasse',
                'glass': 'Glas',
                'jar': 'Glas',
                'can': 'Dose',
                'packet': 'Beutel',
                'pinch': 'Prise',
                'sprig': 'Zweig',
                'clove': 'Zehe',
                'leaf': 'Blatt',
                'slice': 'Scheibe',
                'bunch': 'Bund',
                'piece': 'Stück',
            },
        }

    def _init_language_patterns(self):
        """Initialise tous les patterns de reconnaissance par langue"""
        
        # Patterns d'unités par langue
        self.unit_patterns = {
            Language.FR: [
                # "cuillère à soupe" et variations, y compris "c. à soupe" et "c à soupe"
                (r'\b(cuill[èe]re?s?\s*(?:à|a)\s*soupe|c\.?\s*[àa]\s*soupe|c(?:\.)?\s*[àa]?\s*s(?:\.)?|cas|càs)\b', 'tbsp'),
                # "cuillère à café" et variations sans accents : cuilleres a cafe, c a c, cac
                (r'\b(cuill[èe]re?s?\s*(?:à|a)\s*caf[ée]?|c(?:\.)?\s*[àa]?\s*c(?:\.)?|cac|càc)\b', 'tsp'),
                (r'\b(litres?|l)(?![a-zà-ÿ])\b', 'l'),
                (r'\b(centilitres?|cl)\b', 'cl'),
                (r'\b(millilitres?|ml)\b', 'ml'),
                (r'\b(kilogrammes?|kilos?|kg)\b', 'kg'),
                (r'\b(grammes?|gr|g)(?![a-zà-ÿ])\b', 'g'),
                (r'\b(tasses?)\b', 'cup'),
                (r'\b(verres?)\b', 'glass'),
                (r'\b(pots?)\b', 'jar'),
                (r'\b(boîtes?|boite?s?)\b', 'can'),
                (r'\b(sachets?)\b', 'packet'),
                (r'\b(paquets?)\b', 'package'),
                (r'\b(pincée?s?)\b', 'pinch'),
                (r'\b(branches?)\b', 'sprig'),
                (r'\b(gousses?)\b', 'clove'),
                (r'\b(feuilles?)\b', 'leaf'),
                (r'\b(tranches?)\b', 'slice'),
                (r'\b(bottes?)\b', 'bunch'),
                (r'\b(morceaux?)\b', 'piece'),
            ],
            Language.EN: [
                (r'\b(tablespoons?|tbsps?|tbs|T)\b', 'tbsp'),
                (r'\b(teaspoons?|tsps?|tsp|t)\b', 'tsp'),
                (r'\b(cups?|c)\b', 'cup'),
                (r'\b(lit(?:re|er)s?|l)(?![a-z])\b', 'l'),
                (r'\b(milliliters?|ml)\b', 'ml'),
                (r'\b(kilograms?|kg)\b', 'kg'),
                (r'\b(grams?|g)(?![a-z])\b', 'g'),
                (r'\b(pounds?|lbs?\.?)\b', 'lb'),
                (r'\b(ounces?|oz\.?)\b', 'oz'),
                (r'\b(jars?)\b', 'jar'),
                (r'\b(cans?|tins?)\b', 'can'),
                (r'\b(packets?)\b', 'packet'),
                (r'\b(pinch(?:es)?)\b', 'pinch'),
                (r'\b(sprigs?)\b', 'sprig'),
                (r'\b(cloves?)\b', 'clove'),
                (r'\b(lea(?:f|ves))\b', 'leaf'),
                (r'\b(slices?)\b', 'slice'),
                (r'\b(bunch(?:es)?)\b', 'bunch'),
                (r'\b(pieces?)\b', 'piece'),
            ],
            Language.ES: [
                (r'\b(cucharadas?|cda\.?)\b', 'tbsp'),
                (r'\b(cucharaditas?|cdta\.?)\b', 'tsp'),
                (r'\b(tazas?)\b', 'cup'),
                (r'\b(litros?|l)(?![a-zá-ú])\b', 'l'),
                (r'\b(mililitros?|ml)\b', 'ml'),
                (r'\b(kilogramos?|kg)\b', 'kg'),
                (r'\b(gramos?|g)(?![a-zá-ú])\b', 'g'),
                (r'\b(tarros?)\b', 'jar'),
                (r'\b(latas?)\b', 'can'),
                (r'\b(sobres?)\b', 'packet'),
                (r'\b(pizcas?)\b', 'pinch'),
                (r'\b(ramas?)\b', 'sprig'),
                (r'\b(dientes?)\b', 'clove'),
                (r'\b(hojas?)\b', 'leaf'),
                (r'\b(rodajas?)\b', 'slice'),
                (r'\b(manojos?)\b', 'bunch'),
                (r'\b(trozos?)\b', 'piece'),
            ],
            Language.DE: [
                (r'\b(Esslöffels?|EL)\b', 'tbsp'),
                (r'\b(Teelöffels?|TL)\b', 'tsp'),
                (r'\b(Tassen?)\b', 'cup'),
                (r'\b(Liters?|l)(?![a-zäöüß])\b', 'l'),
                (r'\b(Milliliters?|ml)\b', 'ml'),
                (r'\b(Kilogramms?|kg)\b', 'kg'),
                (r'\b(Gramms?|g)(?![a-zäöüß])\b', 'g'),
                (r'\b(Gläsers?)\b', 'jar'),
                (r'\b(Dosen?)\b', 'can'),
                (r'\b(Beutels?)\b', 'packet'),
                (r'\b(Prisen?)\b', 'pinch'),
                (r'\b(Zweige?)\b', 'sprig'),
                (r'\b(Zehen?)\b', 'clove'),
                (r'\b(Blätter?)\b', 'leaf'),
                (r'\b(Scheiben?)\b', 'slice'),
                (r'\b(Bunde?)\b', 'bunch'),
                (r'\b(Stücke?)\b', 'piece'),
            ]
        }
        
        # Patterns de qualificatifs (améliorés pour mieux détecter les notes)
        self.qualifier_patterns = {
            Language.FR: [
                r'\b(belles?|gros(ses?)?|petit(e?s)?|moyen(ne?s?)?|grand(e?s)?)\b',
                r'\b(frais|fraîche?s?|congelé(e?s)?|surgelé(e?s)?)\b',
                r'\b(bio|biologique)\b',
                r'\b(jaune?s?|rouge?s?|vert(e?s)?|blanc(he?s)?|noir(e?)s?)\b',
                r'\b(haché(e?s)?|émincé(e?s)?|coupé(e?s)?|râpé(e?s)?)\b',
                r'\b(pelé(e?s)?|épluché(e?s)?)\b',
                r'\b(en dés?|en rondelles?|en tranches?)\b',
            ],
            Language.EN: [
                r'\b(large|small|medium|big|tiny)\b',
                r'\b(fresh|frozen|dried)\b',
                r'\b(organic)\b',
                r'\b(yellow|red|green|white|black)\b',
                r'\b(chopped|minced|diced|sliced|grated)\b',
                r'\b(peeled|trimmed)\b',
            ],
            Language.ES: [
                r'\b(grandes?|pequeñ[ao]s?|median[ao]s?)\b',
                r'\b(fresc[ao]s?|congelad[ao]s?)\b',
                r'\b(orgánic[ao]s?)\b',
                r'\b(amarill[ao]s?|roj[ao]s?|verde?s?)\b',
                r'\b(picad[ao]s?|cortad[ao]s?)\b',
                r'\b(pelad[ao]s?)\b',
            ],
            Language.DE: [
                r'\b(groß?e?|klein?e?|mittelgroß?e?)\b',
                r'\b(frisch?e?|gefror(?:en)?e?)\b',
                r'\b(bio)\b',
                r'\b(gelb?e?|rot?e?|grün?e?)\b',
                r'\b(gehackt?e?|gewürfelt?e?)\b',
                r'\b(geschält?e?)\b',
            ]
        }
        
        # PATTERNS pour détecter les notes contextuelles
        self.note_patterns = {
            Language.FR: [
                r'(?:selon|suivant|en fonction de?)\s+(?:leur|la|le|les)\s+(?:taille|grosseur|besoin|goût)',
                r'(?:à|au)\s+(?:votre|ton)\s+(?:goût|convenance)',
                r'(?:plus ou moins)\s+(?:selon|suivant)',
                r'(?:facultatif|optionnel)',
                r'\([^)]+\)',  # Tout entre parenthèses
            ],
            Language.EN: [
                r'(?:according to|depending on)\s+(?:size|taste|preference)',
                r'(?:to taste|optional)',
                r'(?:more or less)',
                r'\([^)]+\)',
            ],
            Language.ES: [
                r'(?:según|dependiendo de)\s+(?:su|el)\s+(?:tamaño|gusto)',
                r'(?:al gusto|opcional)',
                r'\([^)]+\)',
            ],
            Language.DE: [
                r'(?:je nach)\s+(?:Größe|Geschmack)',
                r'(?:nach Geschmack|optional)',
                r'\([^)]+\)',
            ]
        }
        
        # Prépositions à supprimer
        self.preposition_patterns = {
            Language.FR: r"^(?:de|d'|du|des|la|le|les|un|une)\s+",
            Language.EN: r"^(?:of|the|a|an|some)\s+",
            Language.ES: r"^(?:de|del|la|el|los|las|un|una)\s+",
            Language.DE: r"^(?:von|vom|der|die|das|den|dem|ein|eine)\s+"
        }
    
    def build_unit_map(self) -> Dict[str, str]:
        """Construit un dictionnaire de mapping des unités personnalisées"""
        unit_map = {}
        for unit in self.units:
            name = unit.get('name', '').lower()
            code = unit.get('code', '').lower()
            if name:
                unit_map[name] = code
        return unit_map

    def _remove_accents(self, s: str) -> str:
        """Supprime les accents d'une chaîne pour créer des variantes non accentuées."""
        nfkd_form = unicodedata.normalize('NFD', s)
        return ''.join([c for c in nfkd_form if not unicodedata.combining(c)])

    def _alias_to_regex(self, alias: str) -> str:
        """
        Convertit un alias d'unité en une expression régulière. Les alias peuvent
        contenir des parenthèses pour indiquer un pluriel optionnel, par exemple
        "barquette(s)" devient « barquette » ou « barquettes ». Les espaces
        deviennent des séquences d'espaces, et l'expression est encadrée par
        \b pour délimiter les mots.
        """
        # Construction du motif en parcourant la chaîne caractère par caractère
        pattern = ''
        i = 0
        while i < len(alias):
            char = alias[i]
            if char == '(':  # gestion des parenthèses optionnelles
                end = alias.find(')', i)
                # S'il n'y a pas de fermeture, on ignore la parenthèse
                if end == -1:
                    pattern += re.escape(char)
                    i += 1
                    continue
                content = alias[i + 1:end]
                # Ajout du groupe non capturant pour l'option
                pattern += '(?:' + re.escape(content) + ')?'
                i = end + 1
                continue
            else:
                # Échapper tous les autres caractères (accents inclus)
                pattern += re.escape(char)
                i += 1
        # Remplacer les espaces échappés (\ ) par \s+ pour tolérer plusieurs espaces
        pattern = pattern.replace('\\ ', '\\s+')
        # Encadrer avec des limites de mots
        return r'\b' + pattern + r'\b'

    def build_unit_alias_patterns(self) -> Dict[Language, List[Tuple[re.Pattern, str]]]:
        """
        Construit un dictionnaire de patterns dynamiques pour chaque langue. Pour
        chaque unité, on génère une liste de ses alias et de la variante sans
        accent. Chaque alias est converti en expression régulière avec
        _alias_to_regex, puis compilé avec l'option IGNORECASE. Chaque pattern
        est associé au code de l'unité. Exemple: « barquette(s) » et
        « barquettes » donneront un motif pour la langue FR renvoyant le code
        "barquette".
        """
        alias_patterns: Dict[Language, List[Tuple[re.Pattern, str]]] = {lang: [] for lang in Language}
        # Les clés pour accéder aux alias dans les données JSON
        lang_keys = {
            Language.FR: 'aliases_fr',
            Language.EN: 'aliases_en',
            Language.ES: 'aliases_es',
            Language.DE: 'aliases_de',
        }
        for unit in self.units:
            code = unit.get('code', '').lower()
            for lang, key in lang_keys.items():
                aliases = unit.get(key, [])
                for alias in aliases:
                    # Normaliser l'alias: ignorer les alias vides
                    alias = alias.strip()
                    if not alias:
                        continue
                    # Filtrer certains alias qui ne représentent pas des unités
                    # plausibles. On ignore les alias composés de plusieurs mots
                    # lorsque ces mots dépassent 2 caractères (ex: "bouquet garni",
                    # "cube de bouillon", "degré celsius"), car ces chaînes
                    # correspondent le plus souvent à des aliments ou à des
                    # instructions et non à des unités de mesure. Les alias
                    # composés uniquement d'abréviations (c a s, c à s, c. à c.)
                    # sont conservés.
                    alias_clean = alias.replace('(', '').replace(')', '').replace('.', '').strip()
                    words = alias_clean.split()
                    if len(words) > 1 and any(len(w) > 2 for w in words):
                        # ignorer cet alias
                        continue
                    # Générer motif pour l'alias original
                    regex_str = self._alias_to_regex(alias)
                    try:
                        compiled = re.compile(regex_str, flags=re.IGNORECASE)
                        alias_patterns[lang].append((compiled, code))
                    except re.error:
                        # En cas d'erreur de compilation, on ignore l'alias
                        continue
                    # Générer motif pour la version sans accent si différente
                    alias_norm = self._remove_accents(alias)
                    if alias_norm.lower() != alias.lower():
                        # Appliquer le même filtre aux alias normalisés
                        alias_norm_clean = alias_norm.replace('(', '').replace(')', '').replace('.', '').strip()
                        words_norm = alias_norm_clean.split()
                        if not (len(words_norm) > 1 and any(len(w) > 2 for w in words_norm)):
                            regex_str_norm = self._alias_to_regex(alias_norm)
                            try:
                                compiled_norm = re.compile(regex_str_norm, flags=re.IGNORECASE)
                                alias_patterns[lang].append((compiled_norm, code))
                            except re.error:
                                pass
        return alias_patterns
    
    def normalize_text(self, text: str) -> str:
        """Normalise le texte (supprime accents, minuscules, espaces multiples)"""
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def detect_language(self, text: str) -> Language:
        """Détecte la langue du texte"""
        language_scores = {lang: 0 for lang in Language}

        # Les caractères accentués typiquement français sont un signal fort
        # (à, â, ê, è, ë, î, ï, ô, ù, û, ç) — distincts de l'allemand (ä, ö, ü, ß)
        if re.search(r'[àâêèëîïôùûç]', text):
            language_scores[Language.FR] += 3

        for lang in Language:
            # Score basé sur les unités
            for pattern, _ in self.unit_patterns.get(lang, []):
                if re.search(pattern, text, re.IGNORECASE):
                    language_scores[lang] += 2

            # Score basé sur les qualificatifs
            for pattern in self.qualifier_patterns.get(lang, []):
                if re.search(pattern, text, re.IGNORECASE):
                    language_scores[lang] += 1

        detected_lang = max(language_scores, key=language_scores.get)
        return detected_lang if language_scores[detected_lang] > 0 else self.default_language
    
    def extract_quantity(self, text: str) -> Tuple[Optional[float], str]:
        """Extrait la quantité du texte"""
        # Patterns pour détecter les quantités
        quantity_patterns = [
            # Nombres décimaux avec virgule ou point
            r'(\d+(?:[.,]\d+)?)\s*(?:[-àa/]\s*(\d+(?:[.,]\d+)?))?',
            # Fractions avec barre oblique
            r'(\d+)\s*(?:[-/])\s*(\d+)',
            # Fractions Unicode
            r'([¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])',
        ]
        
        # Dictionnaire des fractions Unicode
        fractions = {
            '¼': 0.25, '½': 0.5, '¾': 0.75,
            '⅐': 0.14, '⅑': 0.11, '⅒': 0.1,
            '⅓': 0.33, '⅔': 0.67,
            '⅕': 0.2, '⅖': 0.4, '⅗': 0.6, '⅘': 0.8,
            '⅙': 0.17, '⅚': 0.83,
            '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875
        }
        
        for pattern in quantity_patterns:
            match = re.search(pattern, text)
            if match:
                # Cas fraction Unicode
                if match.group(0) in fractions:
                    quantity = fractions[match.group(0)]
                    remaining = text[match.end():].strip()
                    return quantity, remaining
                
                # Cas nombres décimaux
                try:
                    num1_str = match.group(1).replace(',', '.')
                    num1 = float(num1_str)
                    
                    # Si plage (ex: 2-3)
                    if match.lastindex >= 2 and match.group(2):
                        num2_str = match.group(2).replace(',', '.')
                        num2 = float(num2_str)
                        quantity = (num1 + num2) / 2
                    else:
                        quantity = num1
                    
                    remaining = text[match.end():].strip()
                    return quantity, remaining
                except (ValueError, AttributeError):
                    continue
        
        return None, text
    
    def extract_unit(self, text: str, language: Language) -> Tuple[str, str]:
        """Extrait l'unité du texte"""
        text_for_search = text

        # Pré-check prioritaire : les abréviations de cuillères françaises doivent être
        # détectées AVANT les patterns dynamiques du JSON, car "c" seul peut être aliasé
        # vers une autre unité (ex: celsius, cl) dans units_multilingual_complete.json,
        # ce qui empêcherait de reconnaître "c. à soupe" et "c. à café" correctement.
        if language == Language.FR:
            for pattern, unit_code in [
                (r'\bc\.?\s*[àa]\s*soupe\b', 'tbsp'),
                (r'\bc\.?\s*[àa]\s*caf[ée]?\b', 'tsp'),
            ]:
                match = re.search(pattern, text_for_search, re.IGNORECASE)
                if match:
                    remaining = text_for_search[:match.start()] + text_for_search[match.end():]
                    return unit_code, remaining.strip()

        # Vérifier si le texte contient des expressions à ignorer pour la détection
        # d'unité. Si c'est le cas, on retourne une unité vide et le texte
        # original sans modification. Cela permet, par exemple, d'éviter
        # d'interpréter « bouquet garni » comme une unité « bouquet ».
        for phrase in self.skip_unit_phrases.get(language, []):
            if phrase.lower() in text_for_search.lower():
                return "", text_for_search
        # Étape 1: rechercher dans les patterns dynamiques générés à partir du JSON
        # On parcourt les patterns associés à la langue détectée. Dès qu'un
        # pattern correspond, on renvoie le code et on retire la correspondance du
        # texte. Cela permet de gérer à la fois les pluriels et les alias sans
        # accent.
        for regex, unit_code in self.unit_alias_patterns.get(language, []):
            match = regex.search(text_for_search)
            if match:
                start, end = match.span()
                remaining = text_for_search[:start] + text_for_search[end:]
                # Normaliser le code de l'unité si nécessaire
                normalized = self.unit_code_normalization.get(unit_code.lower(), unit_code)
                return normalized, remaining.strip()
        
        # Étape 2: rechercher dans les patterns standards (abréviations)
        for pattern, standard_unit in self.unit_patterns.get(language, []):
            match = re.search(pattern, text_for_search, re.IGNORECASE)
            if match:
                remaining = text_for_search[:match.start()] + text_for_search[match.end():]
                normalized = self.unit_code_normalization.get(standard_unit.lower(), standard_unit)
                return normalized, remaining.strip()
        
        # Étape 3: rechercher dans les unités personnalisées (mapping simple)
        # Ce mapping est moins complet que celui issu des patterns dynamiques mais
        # reste utile pour les noms d'unités simples définis dans les données
        # (champ name plutôt qu'alias). On effectue une recherche insensible
        # aux majuscules.
        lower_text = text_for_search.lower()
        for custom_name, custom_code in self.unit_map.items():
            if custom_name and custom_name in lower_text:
                idx = lower_text.index(custom_name)
                remaining = text_for_search[:idx] + text_for_search[idx + len(custom_name):]
                normalized = self.unit_code_normalization.get(custom_code.lower(), custom_code)
                return normalized, remaining.strip()
        
        # Aucune unité détectée
        return "", text_for_search
    
    def extract_note(self, text: str, language: Language) -> Tuple[str, str]:
        """Extrait les notes/qualificatifs du texte"""
        notes = []
        remaining = text
        
        # Chercher les patterns de notes
        for pattern in self.note_patterns.get(language, []):
            matches = list(re.finditer(pattern, remaining, re.IGNORECASE))
            for match in reversed(matches):
                note_text = match.group(0).strip()
                if note_text not in notes:
                    notes.append(note_text)
                remaining = remaining[:match.start()] + remaining[match.end():]
        
        combined_note = ', '.join(notes) if notes else ""
        return combined_note, remaining.strip()
    
    def clean_ingredient_name(self, text: str, language: Language) -> str:
        """Nettoie le nom de l'ingrédient"""
        # Normaliser les espaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Supprimer les prépositions en début
        prep_pattern = self.preposition_patterns.get(language, '')
        if prep_pattern:
            text = re.sub(prep_pattern, '', text, flags=re.IGNORECASE)
        
        # Supprimer virgules, points et espaces en début/fin
        text = re.sub(r'^[,\.\s]+|[,\.\s]+$', '', text)
        
        return text.strip()
    
    def parse(self, ingredient_text: str, language: Optional[Language] = None) -> ParsedIngredient:
        """
        Parse un ingrédient complet
        
        Args:
            ingredient_text: Texte de l'ingrédient à parser
            language: Langue à utiliser (auto-détection si None)
        
        Returns:
            ParsedIngredient avec tous les champs extraits
        """
        if not ingredient_text or not isinstance(ingredient_text, str):
            return ParsedIngredient(ingredient="", raw_text=ingredient_text or "")

        # Sauvegarder le texte original
        raw_text = ingredient_text.strip()

        # Supprimer les marqueurs de pluriel de type CuisineAZ : (s), (e), (es)
        text = re.sub(r'\(e?s?\)', '', raw_text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Détection de la langue si non spécifiée
        if language is None:
            language = self.detect_language(text)

        # Extraction séquentielle
        remaining = text
        
        # 1. Extraire la quantité
        quantity, remaining = self.extract_quantity(remaining)
        
        # 2. Extraire l'unité
        unit, remaining = self.extract_unit(remaining, language)

        # Localiser le code d'unité dans la langue détectée
        if unit:
            unit = self.unit_localized_labels.get(language, {}).get(unit, unit)

        # 3. Extraire les notes
        note, remaining = self.extract_note(remaining, language)
        
        # 4. Le reste est le nom de l'ingrédient
        ingredient_name = self.clean_ingredient_name(remaining, language)
        
        return ParsedIngredient(
            ingredient=ingredient_name,
            quantity=quantity,
            unit=unit,
            note=note,
            raw_text=raw_text
        )


# ============================================================================
# APPLICATION FLASK
# ============================================================================

app = Flask(__name__)

# Initialiser le parseur d'ingrédients
# On charge ici le fichier JSON contenant les unités multilingues afin d'ajouter
# les patterns dynamiques. Si le fichier n'est pas disponible ou en cas
# d'erreur, on utilise un parseur sans unités personnalisées.
try:
    with open('units_multilingual_complete.json', 'r', encoding='utf-8') as f:
        units_data = json.load(f)
except Exception:
    units_data = []

ingredient_parser = MultilingualIngredientParser(units=units_data)


@app.route('/', methods=['GET'])
def home():
    """Endpoint de documentation"""
    return jsonify({
        'service': 'Recipe Scraper API',
        'version': '2.0 - Enhanced Schema.org',
        'endpoints': {
            '/scrape': 'GET/POST - Scrape une recette (param: webUrl, parse_ingredients, language)',
            '/parse-ingredient': 'POST - Parse un seul ingrédient (body: ingredient, language)',
            '/parse-ingredients': 'POST - Parse plusieurs ingrédients (body: ingredients[], language)'
        }
    }), 200
    
def extract_recipe_with_extruct(html_content, url):
    """
    Extraction JSON-LD / Microdata via Extruct
    """

    try:
        data = extruct.extract(
            html_content,
            base_url=get_base_url(html_content, url),
            syntaxes=['json-ld', 'microdata']
        )

        recipes = []

        for item in data.get("json-ld", []):

            if isinstance(item, dict):

                recipe_type = item.get("@type")

                if recipe_type == "Recipe":
                    recipes.append(item)

                elif isinstance(recipe_type, list) and "Recipe" in recipe_type:
                    recipes.append(item)

        if recipes:
            return recipes[0]

        return None

    except Exception as e:
        print(f"Extruct error: {e}")
        return None    


@app.route('/scrape', methods=['GET', 'POST'])
def scrape_recipe():
    """
    Scrape une recette depuis une URL et parse automatiquement les ingrédients
    
    Parameters:
        - webUrl (str): URL de la recette à scraper
        - parse_ingredients (bool): Parser les ingrédients (défaut: True)
        - language (str): Langue pour le parsing ('fr', 'en', 'es', 'de', ou 'auto')
    """
    url = None
    parse_ingredients_flag = True
    language = None
    
    if request.method == 'GET':
        url = request.args.get('webUrl')
        parse_ingredients_flag = request.args.get('parse_ingredients', 'true').lower() == 'true'
        language = request.args.get('language', 'auto')
    else:
        data = request.get_json(silent=True) or {}
        url = data.get('webUrl')
        parse_ingredients_flag = data.get('parse_ingredients', True)
        language = data.get('language', 'auto')
    
    if not url:
        return jsonify({
            'success': False,
            'message': 'Missing parameter webUrl',
            'data': {}
        }), 400
    
    try:
        print(f"\n🔍 Scraping: {url}")
        
        # Scraper avec extraction schema.org améliorée
        scraper, enhanced_data = scrape_with_enhanced_schema(url)
        
        def safe_call(method_name):
            """Appel sécurisé des méthodes du scraper"""
            try:
                return getattr(scraper, method_name, lambda: None)()
            except:
                return None
        
        def safe_call_groups():
            """Sérialise ingredient_groups en liste de dicts JSON-compatibles"""
            try:
                groups = scraper.ingredient_groups()
                return [g.__dict__ for g in groups] if groups else None
            except Exception:
                return None

        # Récupérer les données de base du scraper
        result = {
            'title': safe_call('title'),
            'author': safe_call('author'),
            'description': safe_call('description'),
            'host': safe_call('host'),
            'site_name': safe_call('site_name'),
            'canonical_url': safe_call('canonical_url'),
            'language': safe_call('language'),
            'image': safe_call('image'),
            'ingredients': safe_call('ingredients'),
            'ingredient_groups': safe_call_groups(),
            'instructions': safe_call('instructions'),
            'total_time': safe_call('total_time'),
            'yields': safe_call('yields'),
            'prep_time': safe_call('prep_time'),
            'cook_time': safe_call('cook_time'),
            'ratings': safe_call('ratings'),
            'ratings_count': safe_call('ratings_count'),
            'nutrients': safe_call('nutrients'),
            'category': safe_call('category'),
            'cuisine': safe_call('cuisine'),
            'keywords': safe_call('keywords'),
            'equipment': safe_call('equipment'),
            'cooking_method': safe_call('cooking_method'),
            'dietary_restrictions': safe_call('dietary_restrictions'),
        }
        
        # Fusionner avec les données enhanced du schema.org (priorité au schema.org)
        for key, value in enhanced_data.items():
            if value is not None:
                result[key] = value
        
        # Parser les ingrédients si demandé
        if parse_ingredients_flag and result.get('ingredients'):
            # Déterminer la langue
            lang = None
            if language != 'auto':
                try:
                    lang = Language(language)
                except ValueError:
                    pass
            
            parsed_ingredients = []
            for ingredient_text in result['ingredients']:
                parsed = ingredient_parser.parse(ingredient_text, language=lang)
                parsed_ingredients.append({
                    'raw': parsed.raw_text,
                    'ingredient': parsed.ingredient,
                    'quantity': parsed.quantity,
                    'unit': parsed.unit,
                    'note': parsed.note
                })
            
            # Ajouter les ingrédients parsés
            result['ingredients_raw'] = result['ingredients']
            result['ingredients_parsed'] = parsed_ingredients
        
        # Supprimer les valeurs None, vides et dicts vides
        result = {k: v for k, v in result.items() if v not in [None, [], "", {}]}
        
        print(f"✓ Scraping terminé avec succès")
        
        return jsonify({
            'success': True,
            'message': 'Success',
            'data': result
        }), 200
        
    except Exception as e:
        print(f"✗ Erreur: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error scraping URL: {str(e)}',
            'data': {}
        }), 500

@app.route('/scrape-v2', methods=['GET', 'POST'])
def scrape_recipe_v2():

    url = request.args.get('webUrl')

    if not url:
        return jsonify({
            "success": False,
            "message": "Missing webUrl"
        }), 400

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            timeout=20,
            headers=headers
        )

        html_content = response.text

        recipe_data = extract_recipe_with_extruct(
            html_content,
            url
        )

        scraper = scrape_html(
            html_content,
            org_url=url,
            supported_only=False
        )

        def safe_call_v2(method_name):
            try:
                return getattr(scraper, method_name, lambda: None)()
            except Exception:
                return None

        result = {
            "title": safe_call_v2('title'),
            "ingredients": safe_call_v2('ingredients'),
            "instructions": safe_call_v2('instructions'),
            "total_time": safe_call_v2('total_time'),
            "image": safe_call_v2('image'),
            "host": safe_call_v2('host'),
        }

        strategy = "recipe-scrapers"
        score = 50

        if recipe_data:

            strategy = "extruct"

            score += 30

            result["schema_recipe"] = True

            if recipe_data.get("recipeCategory"):
                score += 5

            if recipe_data.get("nutrition"):
                score += 5

            if recipe_data.get("aggregateRating"):
                score += 5

            if recipe_data.get("recipeCuisine"):
                score += 5

        if result.get("ingredients"):
            score += 5

        if result.get("instructions"):
            score += 5

        result["quality_score"] = min(score, 100)
        result["strategy"] = strategy

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/parse-ingredient', methods=['POST'])
def parse_ingredient():
    """
    Parse un seul ingrédient
    
    Body JSON:
        - ingredient (str): Texte de l'ingrédient à parser
        - language (str): Langue ('fr', 'en', 'es', 'de', ou 'auto')
    """
    data = request.get_json(silent=True) or {}
    ingredient_text = data.get('ingredient')
    language = data.get('language', 'auto')
    
    if not ingredient_text:
        return jsonify({
            'success': False,
            'message': 'Missing parameter: ingredient',
            'data': {}
        }), 400
    
    try:
        # Déterminer la langue
        lang = None
        if language != 'auto':
            try:
                lang = Language(language)
            except ValueError:
                pass
        
        # Parser l'ingrédient
        parsed = ingredient_parser.parse(ingredient_text, language=lang)
        detected_language = ingredient_parser.detect_language(ingredient_text)
        
        result = {
            'raw': parsed.raw_text,
            'ingredient': parsed.ingredient,
            'quantity': parsed.quantity,
            'unit': parsed.unit,
            'note': parsed.note,
            'detected_language': detected_language.value
        }
        
        return jsonify({
            'success': True,
            'message': 'Success',
            'data': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error parsing ingredient: {str(e)}',
            'data': {}
        }), 500


@app.route('/parse-ingredients', methods=['POST'])
def parse_ingredients():
    """
    Parse plusieurs ingrédients
    
    Body JSON:
        - ingredients (list): Liste des textes d'ingrédients à parser
        - language (str): Langue ('fr', 'en', 'es', 'de', ou 'auto')
    """
    data = request.get_json(silent=True) or {}
    ingredients = data.get('ingredients', [])
    language = data.get('language', 'auto')
    
    if not ingredients or not isinstance(ingredients, list):
        return jsonify({
            'success': False,
            'message': 'Missing or invalid parameter: ingredients (must be a list)',
            'data': {}
        }), 400
    
    try:
        # Déterminer la langue
        lang = None
        if language != 'auto':
            try:
                lang = Language(language)
            except ValueError:
                pass
        
        # Parser tous les ingrédients
        parsed_list = []
        for ingredient_text in ingredients:
            parsed = ingredient_parser.parse(ingredient_text, language=lang)
            parsed_list.append({
                'raw': parsed.raw_text,
                'ingredient': parsed.ingredient,
                'quantity': parsed.quantity,
                'unit': parsed.unit,
                'note': parsed.note
            })
        
        return jsonify({
            'success': True,
            'message': 'Success',
            'data': {
                'count': len(parsed_list),
                'ingredients': parsed_list
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error parsing ingredients: {str(e)}',
            'data': {}
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)