from datetime import datetime
from layer_raw import RawLayerProcessor
from layer_silver import SilverLayerProcessor
from layer_gold import GoldLayerProcessor
from log_utils import calculate_latency

def main():
    startDateTime = datetime.now()
    print("Worker starting...")
    
    raw_processor = RawLayerProcessor()
    silver_processor = SilverLayerProcessor()
    gold_processor = GoldLayerProcessor()

    raw_processor.run()
    silver_processor.run()
    gold_processor.run()

    endDateTime = datetime.now()
    latency = calculate_latency(startDateTime, endDateTime)
    print(f"Worker Latency: {latency}")

if __name__ == "__main__":
    main()
