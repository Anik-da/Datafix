# Error Pattern Fingerprinting

The analysis route applies `fingerprint_issue` to each actual detector result before returning the analysis. The signature uses issue category, normalized title, inferred column type, issue shape and broad column role; it excludes cell values and row identifiers. Fingerprints group similar detector patterns but do not supply confidence, cause, repair values, or authorization. Decisions and Safety Gate outcomes remain run- and proposal-specific.
