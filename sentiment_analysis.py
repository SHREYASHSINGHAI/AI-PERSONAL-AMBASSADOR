from transformers import pipeline

# Initialize the sentiment analysis pipeline with a specific model.
# This model is pre-trained and fine-tuned for sentiment analysis.
sentiment_analyzer = pipeline("sentiment-analysis", model="finiteautomata/bertweet-base-sentiment-analysis")

def perform_sentiment_analysis(text):
    """
    Performs sentiment analysis on the given text using a pre-trained model.

    Args:
        text (str): The input text to analyze.

    Returns:
        dict: A dictionary containing the sentiment label ('positive', 'negative', 'neutral')
              and the corresponding score.
    """
    if not text.strip():
        return {"label": "neutral", "score": 1.0}
    
    try:
        # The pipeline returns a list of dictionaries, e.g., [{'label': 'POS', 'score': 0.998}]
        result = sentiment_analyzer(text)[0]
        
        # Normalize the label to be consistent
        if result['label'] == 'POS':
            result['label'] = 'positive'
        elif result['label'] == 'NEG':
            result['label'] = 'negative'
        elif result['label'] = 'NEU':
            result['label'] = 'neutral'
            
        return result
    except Exception as e:
        print(f"Error during sentiment analysis: {e}")
        return {"label": "neutral", "score": 0.0}

if __name__ == '__main__':
    # Example usage
    text1 = "I love this new feature, it's amazing!"
    text2 = "I'm not sure if this is what I was expecting."
    text3 = "This is a terrible experience."
    text4 = "The weather is okay today."
    
    print(f"Text: '{text1}' -> Sentiment: {perform_sentiment_analysis(text1)}")
    print(f"Text: '{text2}' -> Sentiment: {perform_sentiment_analysis(text2)}")
    print(f"Text: '{text3}' -> Sentiment: {perform_sentiment_analysis(text3)}")
    print(f"Text: '{text4}' -> Sentiment: {perform_sentiment_analysis(text4)}")
