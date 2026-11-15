def validate_coordinates(ra, dec):

    # Check whether inputs are numbers
    if isinstance(ra, bool) or not isinstance(ra, (int, float)):
        return False

    if isinstance(dec, bool) or not isinstance(dec, (int, float)):
        return False

    # Validate RA
    if not (0 <= ra < 360):
        return False

    # Validate Dec
    if not (-90 <= dec <= 90):
        return False

    return True

