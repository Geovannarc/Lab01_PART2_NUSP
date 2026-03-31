import os
import pandas as pd
from datetime import datetime
from log_utils import get_logger, calculate_latency
from datetime import datetime
from pathlib import Path

class RawLayerProcessor:
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    def run(self):
        start_datetime = datetime.now()
        print("Iniciando ingestão de dados na camada raw")

        input_base = Path(os.getenv("RAW_INPUT_PATH", "C:/source/pos-graduacao"))
        output_base = Path(os.getenv("RAW_OUTPUT_PATH", "C:/source/pos-graduacao"))

        print(f"Input base: {input_base}")
        print(f"Output base: {output_base}")

        input_path = input_base / "archive"
        full_input_path = input_path / "dataset.csv"

        print(f"Full input path: {full_input_path}")

        df = pd.read_csv(full_input_path, engine="pyarrow")

        now = datetime.now()
        year = f"{now.year}"
        month = f"{now.month:02d}"
        day = f"{now.day:02d}"

        output_path = output_base / "data" / "raw" / year / month / day
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = now.strftime("%Y%m%d_%H%M%S")
        file_name = f"dataset_{timestamp}.csv"

        full_output_path = output_path / file_name

        print(f"Full output path: {full_output_path}")

        df.to_csv(full_output_path, index=False)

        end_datetime = datetime.now()
        latency = calculate_latency(start_datetime, end_datetime)

        print(
            f"Camada Raw finalizada. Latência: {latency}. "
            f"Arquivo salvo em: {full_output_path}"
        )

        return str(full_output_path)