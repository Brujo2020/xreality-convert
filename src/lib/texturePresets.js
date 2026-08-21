export const TEXTURE_PRESETS = [
  // 🚗 1. Vehículos Pequeños
  { id: 'veh_small_sport', category: 'Vehículos Pequeños', label: 'Vehículo Deportivo', suffix: ', metallic gloss paint, carbon fiber bodywork, dark tinted glass, chrome trim, pbr materials' },
  { id: 'veh_small_city', category: 'Vehículos Pequeños', label: 'Compacto Urbano', suffix: ', matte pastel paint, satin plastic bumpers, clear headlight lenses, pbr 8k' },
  { id: 'veh_small_moto', category: 'Vehículos Pequeños', label: 'Motocicleta Racing', suffix: ', anodized aluminum frame, high-gloss enamel fuel tank, leather seat, pbr' },
  { id: 'veh_small_scooter', category: 'Vehículos Pequeños', label: 'Scooter Eléctrico', suffix: ', powder-coated steel, rubberized grips, LED acrylic diffusers' },
  { id: 'veh_small_kart', category: 'Vehículos Pequeños', label: 'Kart de Competición', suffix: ', fiberglass shell, raw steel tubular chassis, slick rubber tires' },

  // 🚛 2. Vehículos Grandes & Maquinaria
  { id: 'veh_large_truck', category: 'Vehículos Grandes', label: 'Camión de Carga', suffix: ', weathered industrial paint, steel rims, heavy rubber tread, mud splashes' },
  { id: 'veh_large_crane', category: 'Vehículos Grandes', label: 'Grúa Industrial', suffix: ', high-visibility yellow enamel, grease-stained steel cables, hydraulic chrome pistons' },
  { id: 'veh_large_excavator', category: 'Vehículos Grandes', label: 'Excavadora de Construcción', suffix: ', scratched orange paint, rusted iron tracks, dirt-crusted bucket' },
  { id: 'veh_large_tractor', category: 'Vehículos Grandes', label: 'Tractor Agrícola', suffix: ', gloss red body, muddy oversized tires, cast iron engine block' },
  { id: 'veh_large_bus', category: 'Vehículos Grandes', label: 'Autobús Urbano', suffix: ', high-gloss transit enamel, aluminum window frames, anti-slip rubber floor' },

  // 👤 3. Piel Humana & Personas
  { id: 'skin_realistic', category: 'Piel & Personas', label: 'Piel Humana Realista', suffix: ', realistic human skin, subsurface scattering, skin pore micro-normals, natural skin sheen' },
  { id: 'skin_stylized', category: 'Piel & Personas', label: 'Piel Humana Stylized', suffix: ', clean toon skin shading, soft gradient ramps, smooth subsurface glow' },
  { id: 'skin_mature', category: 'Piel & Personas', label: 'Piel Madura / Texturizada', suffix: ', mature skin texture, fine wrinkles, realistic skin pigmentation, micro-pore normals' },
  { id: 'skin_cyborg', category: 'Piel & Personas', label: 'Rostro Cyborg Híbrido', suffix: ', human skin with integrated chrome implants and glowing fiber optic veins' },
  { id: 'skin_mannequin', category: 'Piel & Personas', label: 'Maniquí de Estudio', suffix: ', matte ceramic skin finish, smooth seamless joints, neutral skin tone' },

  // 🦁 4. Animales & Criaturas
  { id: 'anim_fur', category: 'Animales & Criaturas', label: 'Pelaje Canino / Felino', suffix: ', soft fur strand normals, velvet sheen, wet nose specular map' },
  { id: 'anim_scales', category: 'Animales & Criaturas', label: 'Escamas de Reptil', suffix: ', iridescent reptile scales, deep-crevice occlusion, leathery roughness' },
  { id: 'anim_feathers', category: 'Animales & Criaturas', label: 'Plumas de Ave', suffix: ', layered feather normals, iridescence, glossy barb structure' },
  { id: 'anim_marine', category: 'Animales & Criaturas', label: 'Piel Mamífero Marino', suffix: ', wet glossy skin, specular water droplet layer, subtle blubber SSS' },
  { id: 'anim_insect', category: 'Animales & Criaturas', label: 'Caparazón de Insecto', suffix: ', chitinous metallic sheen, structural color iridescence, micro-groove normals' },

  // 🌿 5. Plantas & Naturaleza
  { id: 'nat_leaf', category: 'Plantas & Naturaleza', label: 'Hojas Tropicales', suffix: ', translucent leaf subsurface scattering, waxy cuticle sheen, vein bump map' },
  { id: 'nat_bark', category: 'Plantas & Naturaleza', label: 'Corteza de Árbol', suffix: ', deep bark ridges, mossy lichen accents, rough organic wood albedo' },
  { id: 'nat_wood', category: 'Plantas & Naturaleza', label: 'Madera Roble / Nogal', suffix: ', polished wood grain, satin varnish sheen, natural ring patterns' },
  { id: 'nat_moss', category: 'Plantas & Naturaleza', label: 'Césped & Musgo', suffix: ', fibrous moss strands, damp earth base, vibrant chlorophyll green' },
  { id: 'nat_flower', category: 'Plantas & Naturaleza', label: 'Flores & Pétalos', suffix: ', soft velvet petal subsurface scattering, delicate vein gradients, pollen dusting' },

  // 🏛️ 6. Arquitectura & Edificación
  { id: 'arch_concrete', category: 'Arquitectura', label: 'Hormigón Visto', suffix: ', formwork concrete textures, micro-pitting, subtle weathering stains' },
  { id: 'arch_brick', category: 'Arquitectura', label: 'Ladrillo Rústico', suffix: ', rough clay brick normals, sand mortar joints, aged efflorescence' },
  { id: 'arch_marble', category: 'Arquitectura', label: 'Mármol Carrara', suffix: ', high-gloss polished marble stone, deep grey veining, crisp specular reflection' },
  { id: 'arch_tile', category: 'Arquitectura', label: 'Teja Cerámica', suffix: ', terracotta clay roughness, sun-baked weathering, interlocking tile pattern' },
  { id: 'arch_glass', category: 'Arquitectura', label: 'Cristal de Fachada', suffix: ', tinted low-E architectural glass, structural silicone joints, reflection blur' },

  // 🪑 7. Muebles & Interiorismo
  { id: 'furn_leather', category: 'Muebles & Interiores', label: 'Cuero Marrón Vintage', suffix: ', patina leather texture, worn edge highlights, subtle stitching bump' },
  { id: 'furn_fabric', category: 'Muebles & Interiores', label: 'Tela Lino / Algodón', suffix: ', woven fabric weave normals, soft fuzz sheen, neutral tone' },
  { id: 'furn_lacquer', category: 'Muebles & Interiores', label: 'Madera Lacada', suffix: ', high-gloss polyurethane lacquer, mirror reflection, seamless finish' },
  { id: 'furn_steel', category: 'Muebles & Interiores', label: 'Metal Inox Cepillado', suffix: ', radial brushed stainless steel, anisotropic reflections, finger-print resistant' },
  { id: 'furn_velvet', category: 'Muebles & Interiores', label: 'Terciopelo Elegante', suffix: ', micro-fiber velvet sheen, dark-light directional pile shift' },

  // 📱 8. Electrónica & Tecnología
  { id: 'tech_aluminum', category: 'Electrónica & Tech', label: 'Aluminio Space Gray', suffix: ', satin anodized aluminum, micro-bead blasted texture, metallic gloss' },
  { id: 'tech_plastic', category: 'Electrónica & Tech', label: 'Plástico ABS Mate', suffix: ', textured electronic housing plastic, anti-glare finish, mold seam lines' },
  { id: 'tech_screen', category: 'Electrónica & Tech', label: 'Pantalla OLED Glass', suffix: ', deep black glass panel, anti-reflective coating, bezel framing' },
  { id: 'tech_pcb', category: 'Electrónica & Tech', label: 'Placa PCB Circuito', suffix: ', green solder mask, copper trace normals, gold-plated contacts' },
  { id: 'tech_carbon', category: 'Electrónica & Tech', label: 'Fibra de Carbono 3K', suffix: ', twill weave carbon fiber, glossy epoxy resin topcoat, anisotropic sheen' },

  // 🤖 9. Sci-Fi, Cyberpunk & Fantasía
  { id: 'scifi_mech', category: 'Sci-Fi & Cyberpunk', label: 'Paneles Mech Sci-Fi', suffix: ', white ceramic composite plating, hazard stripe decals, panel line crevices' },
  { id: 'scifi_cyber', category: 'Sci-Fi & Cyberpunk', label: 'Neon Cyberpunk', suffix: ', dark gunmetal alloy, glowing neon emissive strips, rain streak roughness' },
  { id: 'scifi_titanium', category: 'Sci-Fi & Cyberpunk', label: 'Titanio Quemado', suffix: ', heat-tinted blue gold titanium, iridescence, raw machine finish' },
  { id: 'scifi_holo', category: 'Sci-Fi & Cyberpunk', label: 'Cristal Holográfico', suffix: ', emissive holo-grid pattern, chromatic aberration fringe, energy glow' },
  { id: 'scifi_rust', category: 'Sci-Fi & Cyberpunk', label: 'Metal Oxidado Post-Apoc', suffix: ', heavy rust flakes, peeled paint edges, corroded steel' },

  // 👕 10. Indumentaria & Tejidos
  { id: 'apparel_denim', category: 'Indumentaria & Tejidos', label: 'Denim Jeans', suffix: ', diagonal twill weave denim, washed indigo gradient, seam thread stitching' },
  { id: 'apparel_leather', category: 'Indumentaria & Tejidos', label: 'Cuero Sintético Biker', suffix: ', glossy black polyurethane leather, zipper metal normals' },
  { id: 'apparel_mesh', category: 'Indumentaria & Tejidos', label: 'Tejido Deportivo Mesh', suffix: ', hexagonal mesh perforations, moisture-wicking sheen' },
  { id: 'apparel_silk', category: 'Indumentaria & Tejidos', label: 'Seda / Satén', suffix: ', anisotropic specular luster, fluid drape folds, vibrant hue' },
  { id: 'apparel_canvas', category: 'Indumentaria & Tejidos', label: 'Lona Táctica Militar', suffix: ', cordura nylon weave, camouflage pattern, matte water-repellant coating' },
];
