# LLM Persona Ontology

The LLM Persona Ontology provides a structured model for representing personas used to guide, configure, describe, or evaluate LLM-based agents and roles. It models both Identity (demographic, biographical, and social characteristics) and Behaviour (personality, goals, preferences, reasoning styles, and behavioural constraints), enabling personas to be represented, queried, compared, and edited independently of natural-language prompts.

Rather than describing personas as free-text prompts, it encodes identity, behavioural characteristics, preferences, goals, and constraints as structured RDF knowledge. This enables semantic querying, validation, comparison, reuse, and automatic generation of persona prompts while remaining interoperable with existing Semantic Web vocabularies.

## Design choices

- Main ontology namespace: `https://w3id.org/llm-persona/`.
- Controlled-vocabulary namespace: `https://w3id.org/llm-persona/vocab/`.
- Persona components are organised through two feature pillars: *Identity* and *Behavior*
- Pillar-level properties such as `llmp:hasIdentityFeature` and `llmp:hasBehaviorFeature` organise more specific properties, for example `llmp:hasPersonalIdentity` and `llmp:hasTaskBehavior`.
- Controlled terms are modelled as SKOS concepts in separate vocabularies and referenced from the OWL ontology with `skos:Concept` ranges.
- Reused vocabularies include FOAF, Schema.org, BIO, REL, PROV-O, SKOS, Dublin Core Terms, RDF, RDFS, OWL, and XSD. VANN is used only in SKOS vocabulary files.
- Where possible, LLMP properties are aligned through `rdfs:subPropertyOf`, for example with `schema:affiliation`, `schema:memberOf`, `schema:hasOccupation`, `bio:event`, `foaf:knows`, `rel:parentOf`, and `dcterms:description`.
- Datatypes were refined with `xsd:date`, `xsd:nonNegativeInteger`, `xsd:integer`, `xsd:decimal`, and `rdf:langString`.
- All concept URIs and local names follow PascalCase (UpperCamelCase) naming convention for consistency.

## Files

- `llmp-ontology.ttl`: main OWL ontology in Turtle.
- `llmp-identity-skos.ttl`: identity controlled vocabularies.
- `llmp-behavior-skos.ttl`: behaviour controlled vocabularies.

## Documentation

The documentation has been automatically generated using [OWL Coat](https://github.com/DOREMUS-ANR/OWL-Coat).

Install:

> npm install -g owl-coat

After editing the template in `res`, regenerate the documentation using

> owlcoat generate