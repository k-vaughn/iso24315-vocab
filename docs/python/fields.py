import sys
import xml.etree.ElementTree as ET
import logging

from collections import defaultdict

def extract_class_elements(file_path):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s")
    log = logging.getLogger("fields")
    # Parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Define namespaces if needed (common in OWL/RDF)
    namespaces = {
        'owl': 'http://www.w3.org/2002/07/owl#',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'skos': 'http://www.w3.org/2004/02/skos/core#',
        # Add more namespaces if necessary based on the ontology
    }

    # Find all owl:Class elements
    classes = root.findall('.//owl:Class', namespaces)

    # Collect unique element names (with prefixes)
    unique_elements = set()

    for cls in classes:
        # Iterate over direct children
        for child in cls:
            # Get the tag with prefix (if any)
            tag = child.tag
            # Strip the namespace URI to get prefix:localname
            if '}' in tag:
                ns_uri, local_name = tag.split('}', 1)
                # Find prefix for the namespace
                prefix = next((p for p, uri in namespaces.items() if uri == ns_uri[1:]), '')
                if prefix:
                    tag_name = f"{prefix}:{local_name}"
                else:
                    tag_name = local_name  # Fallback if no prefix found
            else:
                tag_name = tag
            unique_elements.add(tag_name)

    # Alphabetize and return the list
    return sorted(unique_elements)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_rdf_xml_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    elements = extract_class_elements(file_path)
    
    # Output the list
    for elem in elements:
        print(elem)