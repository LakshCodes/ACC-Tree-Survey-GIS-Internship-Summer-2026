# ============================================================
# ACC Tree Inventory — Shade Area Calculator
# ============================================================
# Estimates per-tree shade using crown diameter allometrics:
#   crown_diam_ft = a * DBH_in^b  (species-grouped)
#   crown_area_sqft = pi * (crown_diam_ft / 2)^2
#   effective_shade_sqft = crown_area_sqft * shade_coefficient
# ============================================================

import arcpy
import math

# CONFIG 
TREES_FC = r"C:\Users\Lakshya\Documents\ArcGIS\Packages\Trees3_cb7772\commondata\trees.gdb\Trees_FINAL_V2"   
SPECIES_FIELD = "species"
DBH_FIELD = "DBH_Corrected"    
DISTRICT_FIELD = "district"
# -------------------------------------------------------

FIELDS_TO_ADD = [
    ("Crown_Diam_ft", "DOUBLE", None),
    ("Crown_Area_sqft", "DOUBLE", None),
    ("Shade_Coeff", "DOUBLE", None),
    ("Shade_sqft", "DOUBLE", None),
]

# Crown diameter allometric coefficients by species group
CROWN_COEFFS = {
    "hard_maple_oak_hickory_beech":   (4.70,  0.63),   # wide spreading crowns
    "mixed_hardwood":                 (4.20,  0.61),
    "juniper_oak_mesquite_woodland":  (3.50,  0.55),   # narrower
    "cedar_larch":                    (3.30,  0.58),
    "soft_maple_birch":               (4.30,  0.60),
    "aspen_alder_cottonwood_willow":  (4.50,  0.59),
    "pine":                           (3.00,  0.62),   # conical
    "spruce":                         (2.80,  0.60),
    "true_fir_hemlock":               (2.90,  0.61),
    "douglas_fir":                    (3.00,  0.61),
}

# Shade density coefficients by species group (0-1)
SHADE_COEFFS = {
    "hard_maple_oak_hickory_beech":   0.90,   # live oaks, pecans 
    "mixed_hardwood":                 0.80,   # elms, hackberry, magnolia 
    "juniper_oak_mesquite_woodland":  0.55,   # mesquite sparse, juniper 
    "cedar_larch":                    0.70,   # bald cypress 
    "soft_maple_birch":               0.75,   # maples 
    "aspen_alder_cottonwood_willow":  0.65,   # cottonwood 
    "pine":                           0.60,   # needles 
    "spruce":                         0.70,
    "true_fir_hemlock":               0.72,
    "douglas_fir":                    0.68,
}

DEFAULT_GROUP = "mixed_hardwood"


def add_fields_if_missing(fc):
    existing = [f.name for f in arcpy.ListFields(fc)]
    for fname, ftype, flength in FIELDS_TO_ADD:
        if fname not in existing:
            if flength:
                arcpy.management.AddField(fc, fname, ftype, field_length=flength)
            else:
                arcpy.management.AddField(fc, fname, ftype)
            print(f"Added field: {fname}")
        else:
            print(f"Field already exists, skipping: {fname}")


def calc_shade_fields(fc):
    fields = [
        SPECIES_FIELD, DBH_FIELD, "Species_Group",
        "Crown_Diam_ft", "Crown_Area_sqft", "Shade_Coeff", "Shade_sqft"
    ]
    updated = 0
    skipped = 0

    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            species, dbh_in, group = row[0], row[1], row[2]

            if dbh_in is None or dbh_in <= 0:
                skipped += 1
                continue

            # Use the Species_Group already assigned by the carbon calc
            if not group:
                group = DEFAULT_GROUP

            a, b = CROWN_COEFFS.get(group, CROWN_COEFFS[DEFAULT_GROUP])
            shade_coeff = SHADE_COEFFS.get(group, SHADE_COEFFS[DEFAULT_GROUP])

            crown_diam = a * (dbh_in ** b)
            crown_area = math.pi * (crown_diam / 2) ** 2
            shade_sqft = crown_area * shade_coeff

            row[3] = round(crown_diam, 2)
            row[4] = round(crown_area, 2)
            row[5] = round(shade_coeff, 2)
            row[6] = round(shade_sqft, 2)
            cursor.updateRow(row)
            updated += 1

    print(f"Updated {updated} trees. Skipped {skipped} (missing/invalid DBH).")


def update_district_summary(fc, out_table):
    """Recreates district summary with both carbon AND shade totals."""
    stats_fields = [
        ["CO2_lbs", "SUM"],
        ["Carbon_lbs", "SUM"],
        ["Biomass_lbs", "SUM"],
        ["Shade_sqft", "SUM"],
        ["Crown_Area_sqft", "SUM"],
        ["DBH_Corrected", "MEAN"],
    ]
    if arcpy.Exists(out_table):
        arcpy.management.Delete(out_table)
    arcpy.analysis.Statistics(fc, out_table, stats_fields, case_field=DISTRICT_FIELD)
    print(f"Updated district summary table: {out_table}")


def print_summary(fc):
    total_shade = 0
    total_crown = 0
    count = 0
    with arcpy.da.SearchCursor(fc, ["Shade_sqft", "Crown_Area_sqft"]) as cursor:
        for row in cursor:
            if row[0] is not None:
                total_shade += row[0]
                total_crown += row[1]
                count += 1

    total_shade_acres = total_shade / 43560
    total_crown_acres = total_crown / 43560

    print(f"Shade Summary")
    print(f"Trees with shade values: {count}")
    print(f"Total crown area: {total_crown:,.0f} sqft ({total_crown_acres:.1f} acres)")
    print(f"Total effective shade: {total_shade:,.0f} sqft ({total_shade_acres:.1f} acres)")
    print(f"Average shade per tree: {total_shade / count:,.1f} sqft")


if __name__ == "__main__":
    print("Step 1: Adding shade fields")
    add_fields_if_missing(TREES_FC)

    print("\nStep 2: Calculating shade fields")
    calc_shade_fields(TREES_FC)

    print("\nStep 3: Summary check...")
    print_summary(TREES_FC)

    print("\nStep 4: Updating district summary table")
    workspace = arcpy.Describe(TREES_FC).path
    out_table = f"{workspace}\\Trees_Carbon_By_District"
    update_district_summary(TREES_FC, out_table)

    print("\nDone.")
