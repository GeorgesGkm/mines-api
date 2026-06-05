import enum
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, Float, Date, DateTime, ForeignKey, Table, Enum
from sqlalchemy.orm import relationship
from src.core.database import Base

# --- TABLES INTERMÉDIAIRES (Jointures) ---

# Table d'association pour la relation Plus-à-Plus entre Mission et Agent
mission_agent = Table(
    'mission_agent',
    Base.metadata,
    Column('mission_id', Integer, ForeignKey('mission.n_ordre'), primary_key=True),
    Column('agent_id', String(50), ForeignKey('agent.matricule'), primary_key=True)
)


# --- MODÈLES DE DONNÉES ---

class Agent(Base):
    __tablename__ = "agent"

    matricule = Column(String(50), primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    postnom = Column(String(100))
    prenom = Column(String(100))
    fonction = Column(String(100))
    grade = Column(String(50))  # Un agent a un seul grade

    # Relations
    missions = relationship("Mission", secondary=mission_agent, back_populates="agents")

    #User compte
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 
    user_rattache = relationship("User", back_populates="agent")


class Mission(Base):
    __tablename__ = "mission"

    n_ordre = Column(Integer, primary_key=True, index=True, autoincrement=True)
    objet = Column(String(255), nullable=False)
    province = Column(String(100), nullable=False)
    date_debut = Column(Date)
    date_fin = Column(Date)
    statut = Column(String(50), default="PROPOSE") # PROPOSE, VALIDE_DIR, APPROUVE_SG, SIGNE_MINISTRE, RETIRE, EN_COURS, CLOTURE 
    commentaire = Column(String(255), nullable=True)
    date_cloture = Column(Date, nullable=True)
    mode_transport = Column(String(100), nullable=False)
    note_explicative = Column(String, nullable=True) # Texte ou lien vers le document de l'agent

    # Clé étrangère vers Entreprise
    entreprise_code = Column(String(50), ForeignKey('entreprise.code'))
    
    # Relations
    entreprise = relationship("Entreprise", back_populates="missions")
    agents = relationship("Agent", secondary=mission_agent, back_populates="missions")
    proces_verbal = relationship("ProcesVerbal", uselist=False, back_populates="mission")


class TypePV(Base):
    __tablename__ = "type_pv"

    code_type = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type_nom = Column(String(100), nullable=False)

    # Relations
    pvs = relationship("ProcesVerbal", back_populates="type_relation")


class ProcesVerbal(Base):
    __tablename__ = "proces_verbal"

    num_pv = Column(String(50), primary_key=True, index=True)
    date_pv = Column(Date, nullable=False)
    infraction = Column(String(255))
    montant_amande = Column(Float)
    
    # Clés étrangères (One-to-One avec Mission, Many-to-One avec Type)
    mission_id = Column(Integer, ForeignKey('mission.n_ordre'), unique=True)
    type_code = Column(Integer, ForeignKey('type_pv.code_type'))

    # Relations
    mission = relationship("Mission", back_populates="proces_verbal")
    type_relation = relationship("TypePV", back_populates="pvs")
    questions_reponses = relationship("QuestionReponse", back_populates="proces_verbal", cascade="all, delete-orphan")


class QuestionReponse(Base):
    __tablename__ = "question_reponse"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    num_ordre = Column(Integer, nullable=False)
    question = Column(String, nullable=False)
    response = Column(String, nullable=False)
    
    # Clé étrangère vers PV
    num_pv = Column(String(50), ForeignKey('proces_verbal.num_pv'))

    # Relations
    proces_verbal = relationship("ProcesVerbal", back_populates="questions_reponses")


class Entreprise(Base):
    __tablename__ = "entreprise"

    code = Column(String(50), primary_key=True, index=True)
    nomenclature = Column(String(255))
    rccm = Column(String(100))
    idnat = Column(String(100))
    adresse = Column(String(255))
    n_impot = Column(String(100))
    province = Column(String(100))
    phone = Column(String(50))
    n_comptebancaire = Column(String(100))

    # Relations
    missions = relationship("Mission", back_populates="entreprise")
    productions = relationship("Production", back_populates="entreprise")
    demandes = relationship("Demande", back_populates="entreprise")


class ProductionSubstance(Base):
    """ Table d'association avec des attributs pour Production et Substance """
    __tablename__ = "production_substance"

    production_code = Column(String(50), ForeignKey('production.code_prod'), primary_key=True)
    substance_code = Column(Integer, ForeignKey('substance.code_sub'), primary_key=True)
    
    centre_ach = Column(String(100))
    nb_exp = Column(Integer)
    valbon = Column(Float)
    val_decl = Column(Float)
    mpc_decl = Column(Integer)

    # Relations vers les entités physiques
    production = relationship("Production", back_populates="substances")
    substance = relationship("Substance", back_populates="productions")


class Production(Base):
    __tablename__ = "production"

    code_prod = Column(String(50), primary_key=True, index=True)
    datprod = Column(Date, nullable=False)
    nbCarat = Column(Float)
    
    # Clé étrangère vers Entreprise
    entreprise_code = Column(String(50), ForeignKey('entreprise.code'))

    # Clé étrangère vers la Mission
    mission_id = Column(Integer, ForeignKey('mission.n_ordre'), nullable=False)

    # Relations
    entreprise = relationship("Entreprise", back_populates="productions")
    substances = relationship("ProductionSubstance", back_populates="production")
    # Optionnel 
    mission = relationship("Mission")


class Substance(Base):
    __tablename__ = "substance"

    code_sub = Column(Integer, primary_key=True, index=True, autoincrement=True)
    libSub = Column(String(50))
    mont = Column(Float)
    carat = Column(Float)
    date_cont = Column(Date)

    # Relations
    productions = relationship("ProductionSubstance", back_populates="substance")


class StatutInstruction(str, enum.Enum):
    DEPOT = "DEPOT_DIRECTION_MINES"
    ANALYSE_PROVINCIALE = "EN_COURS_DIVISION_PROVINCIALE"
    ANALYSE_MINISTRE_PROV = "EN_COURS_MINISTRE_PROVINCIAL"
    ANALYSE_DIRECTION_MINES = "EN_COURS_DIRECTION_MINES"
    VALIDE = "VALIDE_ET_TRANSMIS_CAMI"
    REJETE = "REJETE"

class TypeAvis(str, enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    FAVORABLE = "FAVORABLE"
    DEFAVORABLE = "DEFAVORABLE"


class Demande(Base):
    __tablename__ = "demande"

    numdem = Column(String(50), primary_key=True, index=True)
    datdem = Column(Date, nullable=False, default=date.today)
    
    # ─── AJOUTS CRITIQUES POUR LE PROCESSUS DE TERRAIN ───
    statut = Column(Enum(StatutInstruction), default=StatutInstruction.DEPOT, nullable=False)
    
    # Suivi des avis de chaque niveau étatique
    avis_division_provinciale = Column(Enum(TypeAvis), default=TypeAvis.EN_ATTENTE, nullable=False)
    date_avis_div_prov = Column(DateTime, nullable=True)
    
    avis_ministre_provincial = Column(Enum(TypeAvis), default=TypeAvis.EN_ATTENTE, nullable=False)
    date_avis_min_prov = Column(DateTime, nullable=True)
    
    avis_direction_mines = Column(Enum(TypeAvis), default=TypeAvis.EN_ATTENTE, nullable=False)
    date_avis_dir_mines = Column(DateTime, nullable=True)
    
    # Clé étrangère (Relation EFFECTUER 1,1)
    entreprise_code = Column(String(50), ForeignKey('entreprise.code'), nullable=False)

    # Relations
    entreprise = relationship("Entreprise", back_populates="demandes")
    titre_minier = relationship("TitreMinier", back_populates="demande", uselist=False)
    documents_scannes = relationship("DocumentScanne", back_populates="demande", cascade="all, delete-orphan")


class TitreMinier(Base):
    __tablename__ = "titre_minier"

    naretag = Column(String(100), primary_key=True, index=True) # N° Arrêté d'octroi ou renouvellement
    ndocetudfai = Column(String(100))  # N° Référence Étude Faisabilité
    ndocimpenv = Column(String(100))   # N° Référence Étude Impact Env.
    datoctroitit = Column(Date, nullable=True)
    datfinval = Column(Date, nullable=True)

    # Clé étrangère (Relation ABOUTIR 1,1)
    demande_num = Column(String(50), ForeignKey('demande.numdem'), nullable=True)
    
    # Clé étrangère (Relation SE TROUVER 1,1)
    codetattit = Column(Integer, ForeignKey('etat_titre.codetattit'), nullable=False)
    
    # Clé étrangère (Relation ETRE2 1,1)
    codtyptit = Column(Integer, ForeignKey('type_titre.codtyptit'), nullable=False)

    # Relations
    demande = relationship("Demande", back_populates="titre_minier")
    etat = relationship("EtatTitre", back_populates="titres")
    type_titre = relationship("TypeTitre", back_populates="titres")


class EtatTitre(Base):
    __tablename__ = "etat_titre"

    codetattit = Column(Integer, primary_key=True, autoincrement=True)
    libetattit = Column(String(50), nullable=False) # "Renouvelé", "Déchu", "Refusé", "En cours"

    titres = relationship("TitreMinier", back_populates="etat")


class TypeTitre(Base):
    __tablename__ = "type_titre"

    codtyptit = Column(Integer, primary_key=True, autoincrement=True)
    libtyptit = Column(String(100), nullable=False) # "Permis d'Exploitation (PE)", "Permis de Recherche (PR)"

    titres = relationship("TitreMinier", back_populates="type_titre")


class DocumentScanne(Base):
    __tablename__ = "document_scanne"

    id = Column(Integer, primary_key=True, autoincrement=True)
    demande_num = Column(String(50), ForeignKey('demande.numdem'), nullable=False)
    
    type_fichier = Column(String(50), nullable=False) # "AGREMENT", "ETUDE_FAISABILITE", "ETUDE_IMPACT"
    nom_fichier = Column(String(150), nullable=False) # "etude_impact_pe1245.pdf"
    chemin_stockage = Column(String(255), nullable=False) # "/uploads/documents/2026/..."
    date_upload = Column(DateTime, default=datetime.utcnow)

    demande = relationship("Demande", back_populates="documents_scannes")