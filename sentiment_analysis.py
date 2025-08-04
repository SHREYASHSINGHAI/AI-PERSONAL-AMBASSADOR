def perform_sentiment_analysis_lazy_load(text, pipeline):
    """
    Performs sentiment analysis on a given text using a pre-loaded pipeline.
    """
    results = pipeline(text)
    return results[0]
