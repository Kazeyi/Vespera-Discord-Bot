from enum import Enum

class VoidCyclePhase(Enum):
    """Enum for campaign phases"""
    PHASE_1 = 1  # Founder Era - Medieval High Fantasy
    PHASE_2 = 2  # Legend Era - Transition & Convergence
    PHASE_3 = 3  # Integrated Era - Sci-Fantasy Civilization


class SpecializationPath(Enum):
    """Phase 3 specialization paths"""
    AURA_ACCELERATION = "aura"      # Bio-energy, neural conductors, physical overclocking
    SYSTEMATIC_SORCERY = "sorcery"  # Mana algorithms, spell sequences, logic-based magic
    UNSPECIALIZED = "unspecialized" # Not yet chosen (Phase 1/2)


class SessionModeManager:
    """Manages session modes: Architect vs Scribe"""
    ARCHITECT = "architect" 
    SCRIBE = "scribe"

class PhaseManager:
    """Manages campaign phases and world evolution across 1000+ years"""

    PHASE_DESCRIPTIONS = {
        VoidCyclePhase.PHASE_1: {
            "name": "The Founder Era",
            "years": "Year 0",
            "theme": "Classic Sword & Magic",
            "description": "Kingdoms are established. Bloodlines are born. Heroes become legends.",
            "available_systems": ["all"],
            "magic_style": "Chaotic Chants & Incantations",
            "tech_style": "Medieval Craftsmanship"
        },
        VoidCyclePhase.PHASE_2: {
            "name": "The Legend Era",
            "years": "Year 20-50",
            "theme": "Convergence & Consequences",
            "description": "Direct descendants live with the consequences of P1. Early signs of magical convergence.",
            "available_systems": ["all"],
            "magic_style": "Ritualized & Systematic Spellcasting",
            "tech_style": "Hybrid Enchanted Craftsmanship"
        },
        VoidCyclePhase.PHASE_3: {
            "name": "The Integrated Era",
            "years": "Year 500-1000+",
            "theme": "Sci-Fantasy Civilization",
            "description": "A modern world where sword & magic are unified into systematic disciplines. Tech optimizes magic.",
            "available_systems": ["aura", "sorcery"],
            "magic_style": "Calculated Execution Sequences",
            "tech_style": "Bio-Neural Integration & Mana Circuits"
        }
    }

    @staticmethod
    def get_phase_info(phase: VoidCyclePhase) -> dict:
        """Get phase metadata"""
        return PhaseManager.PHASE_DESCRIPTIONS.get(phase, {})

    @staticmethod
    def time_skip_options(current_phase: VoidCyclePhase) -> dict:
        """Time skip options when advancing phases"""
        if current_phase == VoidCyclePhase.PHASE_1:
            return {"short": 20, "long": 30, "description": "20-30 years"}
        if current_phase == VoidCyclePhase.PHASE_2:
            return {"short": 500, "long": 1000, "description": "500-1000 years"}
        return {"short": 0, "long": 0, "description": "Campaign end"}


class BloodlineManager:
    """
    Manages ancestral inheritance and specialization locking.
    """

    MARTIAL_CLASSES = {"Barbarian", "Fighter", "Paladin", "Ranger", "Rogue", "Monk"}
    CASTER_CLASSES = {"Wizard", "Cleric", "Druid", "Sorcerer", "Warlock", "Bard"}

    @staticmethod
    def classify_ancestor(class_name: str) -> str:
        """Classify if ancestor was martial, caster, or dual"""
        martial = class_name in BloodlineManager.MARTIAL_CLASSES
        caster = class_name in BloodlineManager.CASTER_CLASSES
        
        if martial and caster: return "Hybrid"
        if martial: return "Martial"
        if caster: return "Caster"
        return "Specialist"


class UniquePointSystem:
    """
    Defines the world's unique environmental point and how it affects Phase 3 tech/magic.
    """

    UNIQUE_POINTS = {
        "volcano": {
            "name": "The Magma Core",
            "element": "fire",
            "phase3_law": "Geothermal Mana Conversion: All spells gain +1 fire damage. Aura conductors use thermal bio-circulation.",
            "tech_style": "Heat-Resonant Circuitry",
            "description": "A world where fire and heat are the primary mana source"
        },
        "ocean": {
            "name": "The Hydro Nexus",
            "element": "water",
            "phase3_law": "Hydro-Pressure Circuits: Water is a high-speed mana conductor. Metal becomes heavy and slow.",
            "tech_style": "Fluid-Dynamic Neural Networks",
            "description": "A world where water conducts magic at unprecedented speeds"
        },
        "floating_islands": {
            "name": "The Aether Pillars",
            "element": "air",
            "phase3_law": "Anti-Gravity Resonance: Levitation costs half mana. Projectiles travel twice as far.",
            "tech_style": "Gravity-Null Processors",
            "description": "A world suspended between sky and earth, where gravity is negotiable"
        },
        "eternal_tundra": {
            "name": "The Frost Throne",
            "element": "ice",
            "phase3_law": "Cryo-Stasis Field: Time flows slower. Potions last 2x longer. Spell durations doubled.",
            "tech_style": "Temporal-Stasis Conduits",
            "description": "A world locked in eternal winter, where time itself slows"
        },
        "ancient_forest": {
            "name": "The Life Root",
            "element": "nature",
            "phase3_law": "Bio-Synthesis Codex: Healing spells gain +2 HP. Plants can be woven into technology.",
            "tech_style": "Organic Neural Systems",
            "description": "A world where nature and technology are one"
        },
        "crystal_caverns": {
            "name": "The Prismatic Core",
            "element": "crystal",
            "phase3_law": "Lattice Amplification: All spell damage amplified by 20%. Mana regeneration +1/turn.",
            "tech_style": "Crystalline Quantum Processors",
            "description": "A world of living crystals that amplify all magic"
        },
        "shadow_realm": {
            "name": "The Umbral Veil",
            "element": "shadow",
            "phase3_law": "Void-Touch Interface: Stealth gains permanent advantage. Shadow magic damage doubled.",
            "tech_style": "Entropy-Aligned Circuitry",
            "description": "A world where darkness is tangible and can be manipulated"
        },
        "starfall_plains": {
            "name": "The Celestial Compass",
            "element": "cosmic",
            "phase3_law": "Starlight Navigation: All detection spells have +30 ft range. Teleportation more reliable.",
            "tech_style": "Astral-Aligned Conductors",
            "description": "A world touched by celestial forces"
        },
        "sandstorm_wastes": {
            "name": "The Dune Furnace",
            "element": "sand",
            "phase3_law": "Erosion-Based Logic: Mana pools regenerate naturally. Constructs gain durability.",
            "tech_style": "Sandstone-Etched Algorithms",
            "description": "A world shaped by endless storms and transformation"
        },
        "thunderpeak": {
            "name": "The Storm Crown",
            "element": "lightning",
            "phase3_law": "Electrical Synchronization: All spells cast at haste speed. Initiative gains +3.",
            "tech_style": "Tesla-Resonant Networks",
            "description": "A world where lightning and electricity are sentient forces"
        },
        "mushroom_kingdom": {
            "name": "The Spore Garden",
            "element": "fungi",
            "phase3_law": "Mycelial Network: Party telepathy within 1 mile. Poison damage doubled.",
            "tech_style": "Fungal-Neural Interfaces",
            "description": "A world of bioluminescent mushrooms and interconnected consciousness"
        },
        "clockwork_city": {
            "name": "The Gear Nexus",
            "element": "machinery",
            "phase3_law": "Temporal Acceleration: Action economy +1 free action/turn. Mana refills on short rest.",
            "tech_style": "Perpetual Motion Engines",
            "description": "A world where magic and machinery are indistinguishable"
        }
    }

    @staticmethod
    def get_unique_point(point_name: str) -> dict:
        """Get unique point details"""
        return UniquePointSystem.UNIQUE_POINTS.get(point_name, {})

    @staticmethod
    def list_unique_points() -> list:
        """List all available unique points"""
        return list(UniquePointSystem.UNIQUE_POINTS.keys())


class AuraAccelerationSystem:
    """Phase 3 specialization path: internal bio-energy and physical overclocking."""

    SPECIALIZATION_TREES = {
        "tier_1": {
            "name": "Neural Awakening",
            "abilities": [
                {"name": "Synapse Surge", "effect": "Melee attacks gain +1d6 damage"},
                {"name": "Bio-Resonance", "effect": "Damage resistance to one element of choice"},
                {"name": "Nervous Overload", "effect": "Gain advantage on initiative rolls"}
            ]
        },
        "tier_2": {
            "name": "Circuit Mastery",
            "abilities": [
                {"name": "High-Frequency Strike", "effect": "Attacks bypass resistance (not immunity)"},
                {"name": "Aura Fortification", "effect": "+5 to AC when not wearing armor"},
                {"name": "Neural Echo", "effect": "Can make an extra attack as bonus action 1/turn"}
            ]
        },
        "tier_3": {
            "name": "Ascended Conductor",
            "abilities": [
                {"name": "Perfect Synchronization", "effect": "All attacks have advantage for 1 minute (recharge: long rest)"},
                {"name": "Body as Weapon", "effect": "Unarmed damage dice increases to d12"},
                {"name": "Aura Explosion", "effect": "AOE damage burst (recharge: long rest)"}
            ]
        }
    }

    @staticmethod
    def get_tier_abilities(tier: str) -> list:
        """Get abilities for a tier"""
        tree = AuraAccelerationSystem.SPECIALIZATION_TREES.get(tier, {})
        return tree.get("abilities", [])


class SystematicSorcerySystem:
    """Phase 3 specialization path: external mana manipulation and logical calculation."""

    SPECIALIZATION_TREES = {
        "tier_1": {
            "name": "Algorithm Foundation",
            "abilities": [
                {"name": "Spell Compilation", "effect": "Cast one spell as bonus action 1/turn"},
                {"name": "Mana Optimization", "effect": "-1 spell slot cost on all spells"},
                {"name": "Sequence Parsing", "effect": "Learn one additional spell from any school"}
            ]
        },
        "tier_2": {
            "name": "Logical Execution",
            "abilities": [
                {"name": "Parallel Casting", "effect": "Cast two cantrips per action"},
                {"name": "Error Correction", "effect": "Reroll one failed spell save 1/turn"},
                {"name": "Spell Amplification", "effect": "Spell damage increased by 1d8"}
            ]
        },
        "tier_3": {
            "name": "Sequence Ascension",
            "abilities": [
                {"name": "Reality Compilation", "effect": "Cast any spell at advantage (recharge: long rest)"},
                {"name": "Cascading Logic", "effect": "One spell can trigger another spell free (recharge: long rest)"},
                {"name": "Mana Singularity", "effect": "Recover 1 spell slot on short rest"}
            ]
        }
    }

    @staticmethod
    def get_tier_abilities(tier: str) -> list:
        """Get abilities for a tier"""
        tree = SystematicSorcerySystem.SPECIALIZATION_TREES.get(tier, {})
        return tree.get("abilities", [])

