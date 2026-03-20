import os

import numpy as np

def import_sdt(file_path: str):
    """
    Imports Becker & Hickl SDT files.
    Maps data into a [Y, X, T, C]-style structure for the Python backend.
    """
    try:
        from sdtfile import SdtFile
    except ImportError as exc:
        raise RuntimeError(
            "SDT import requires the optional 'sdtfile' package. "
            "Install it to enable Becker & Hickl file import."
        ) from exc

    sdt = SdtFile(file_path)
    
    # sdt.data is a list of arrays (one per channel/series)
    # Typically [Channel, Y, X, T] or [Series, Y, X, T]
    raw_data_list = sdt.data
    
    # For now, we take the first available data block
    # and transpose to [Y, X, T] for internal engine use (C=1)
    data = raw_data_list[0] # assuming (Y, X, T)
    
    # Metadata extraction
    # tac_range is usually in the info/measure_info
    tac_range = 12.5 # Default
    try:
        # Becker & Hickl TAC range (ns)
        tac_range = sdt.measure_info[0]["tac_range"] * 1e9
    except:
        pass
        
    n_gates = data.shape[2]
    
    return data, {
        "tac_range": tac_range,
        "n_gates": n_gates,
        "filename": os.path.basename(file_path)
    }
