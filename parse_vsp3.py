import xml.etree.ElementTree as ET
tree = ET.parse('test_fuse.vsp3')
root = tree.getroot()
for geom in root.findall('.//Vehicle/Geom'):
    print(f"Geom Type: {geom.find('ParmContainer/Name').text if geom.find('ParmContainer/Name') is not None else 'Unknown'}")
    for pc in geom.findall('.//ParmContainer'):
        group = pc.get('GroupName')
        if not group: continue
        for p in pc.findall('.//Parm'):
            print(f"  Group: {group}, Parm: {p.get('Name')}")
