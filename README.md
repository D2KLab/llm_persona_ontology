# LLM Persona Ontology

The LLM Persona Ontology provides a structured model for representing personas used to guide, configure, describe, or evaluate LLM-based agents and roles. It organises persona information around the identity and behaviour pillars.

## Design choices

- Main ontology namespace: `http://example.org/llmp#`.
- Controlled-vocabulary namespace: `http://example.org/llmp/vocab/`.
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
