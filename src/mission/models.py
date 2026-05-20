from sqlalchemy import Column, String, Integer, Float, Date, ForeignKey, Table
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


class Mission(Base):
    __tablename__ = "mission"

    n_ordre = Column(Integer, primary_key=True, index=True, autoincrement=True)
    objet = Column(String(255), nullable=False)
    province = Column(String(100), nullable=False)
    date_debut = Column(Date)
    date_fin = Column(Date)
    statut = Column(String(50), default="PROPOSE") # PROPOSE, VALIDE_DIR, APPROUVE_SG, SIGNE_MINISTRE, RETIRE, EN_COURS, CLOTURE    mode_transport = Column(String(100))
    date_signature = Column(Date, nullable=True)
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

    code_type = Column(String(50), primary_key=True, index=True)
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
    type_code = Column(String(50), ForeignKey('type_pv.code_type'))

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
    titres_miniers = relationship("TitreMinier", back_populates="entreprise")


class ProductionSubstance(Base):
    """ Table d'association avec des attributs pour Production et Substance """
    __tablename__ = "production_substance"

    production_code = Column(String(50), ForeignKey('production.code_prod'), primary_key=True)
    substance_contrat = Column(String(50), ForeignKey('substance.num_contrat'), primary_key=True)
    
    centre_ach = Column(String(100))
    nb_achet = Column(Integer)
    nb_exploit = Column(Integer)
    valbon = Column(Float)
    val_decl = Column(Float)
    mpc_decl = Column(String(100))

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

    # Relations
    entreprise = relationship("Entreprise", back_populates="productions")
    substances = relationship("ProductionSubstance", back_populates="production")


class Substance(Base):
    __tablename__ = "substance"

    num_contrat = Column(String(50), primary_key=True, index=True)
    date_cont = Column(Date)
    annee_cont = Column(Integer)

    # Relations
    productions = relationship("ProductionSubstance", back_populates="substance")


class TypeTitre(Base):
    __tablename__ = "type_titre"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name_type = Column(String(100), nullable=False)

    # Relations
    titres = relationship("TitreMinier", back_populates="type_relation")


class TitreMinier(Base):
    __tablename__ = "titre_minier"

    numArret = Column(String(50), primary_key=True, index=True)
    doc_etude = Column(String(255))
    doc_impactEnvir = Column(String(255))
    date_octroi = Column(Date)
    date_fin = Column(Date)
    etat = Column(String(50))

    # Clés étrangères
    entreprise_code = Column(String(50), ForeignKey('entreprise.code'))
    type_id = Column(Integer, ForeignKey('type_titre.id'))

    # Relations
    entreprise = relationship("Entreprise", back_populates="titres_miniers")
    type_relation = relationship("TypeTitre", back_populates="titres")