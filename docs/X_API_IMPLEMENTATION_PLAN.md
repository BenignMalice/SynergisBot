# 🐦 X API Implementation Plan for MoneyBot

## 🎯 **Immediate Implementation (Free Tier)**

### **Step 1: Basic X API Integration**

Create `infra/x_sentiment_service.py`:

```python
import tweepy
import openai
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

class XSentimentService:
    def __init__(self, bearer_token: str, openai_api_key: str):
        self.client = tweepy.Client(
            bearer_token=bearer_token,
            wait_on_rate_limit=True
        )
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
    
    def get_symbol_sentiment(self, symbol: str, hours_back: int = 24) -> Dict:
        """Get sentiment for specific trading symbol"""
        try:
            # Search for tweets mentioning the symbol
            tweets = self.client.search_recent_tweets(
                query=f"${symbol} OR #{symbol}",
                max_results=100,
                tweet_fields=['created_at', 'public_metrics', 'author_id'],
                start_time=datetime.utcnow() - timedelta(hours=hours_back)
            )
            
            if not tweets.data:
                return {
                    'score': 0.0,
                    'confidence': 0.0,
                    'tweet_count': 0,
                    'sentiment': 'NEUTRAL'
                }
            
            # Analyze sentiment using GPT-4
            sentiment_analysis = self._analyze_tweets_sentiment(tweets.data)
            
            return {
                'score': sentiment_analysis['score'],
                'confidence': sentiment_analysis['confidence'],
                'tweet_count': len(tweets.data),
                'sentiment': sentiment_analysis['sentiment'],
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Error getting X sentiment for {symbol}: {e}")
            return {
                'score': 0.0,
                'confidence': 0.0,
                'tweet_count': 0,
                'sentiment': 'NEUTRAL',
                'error': str(e)
            }
    
    def _analyze_tweets_sentiment(self, tweets: List) -> Dict:
        """Use GPT-4 to analyze tweet sentiment"""
        # Prepare tweets for analysis
        tweet_texts = [tweet.text for tweet in tweets[:50]]  # Limit to 50 tweets
        
        prompt = f"""
        Analyze the sentiment of these tweets about trading/finance:
        
        {json.dumps(tweet_texts, indent=2)}
        
        Return a JSON response with:
        - score: -1.0 to 1.0 (negative to positive)
        - confidence: 0.0 to 1.0 (how confident in the analysis)
        - sentiment: "BULLISH", "BEARISH", or "NEUTRAL"
        - key_themes: List of main themes mentioned
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error analyzing tweets: {e}")
            return {
                'score': 0.0,
                'confidence': 0.0,
                'sentiment': 'NEUTRAL',
                'key_themes': []
            }
```

### **Step 2: Update News Service**

Modify `infra/news_service.py`:

```python
# Add to NewsEvent dataclass
@dataclass
class NewsEvent:
    # ... existing fields ...
    x_sentiment: Optional[Dict] = None
    social_volume: int = 0
    influencer_impact: str = "LOW"

# Add X sentiment integration
def enhance_with_x_sentiment(self, event: NewsEvent, x_service: XSentimentService):
    """Enhance news event with X sentiment"""
    try:
        # Get sentiment for related symbols
        symbol_sentiment = {}
        for symbol in event.symbols:
            sentiment = x_service.get_symbol_sentiment(symbol)
            symbol_sentiment[symbol] = sentiment
        
        # Calculate overall sentiment
        if symbol_sentiment:
            scores = [s['score'] for s in symbol_sentiment.values() if s['score'] != 0]
            if scores:
                avg_score = sum(scores) / len(scores)
                event.x_sentiment = {
                    'overall_score': avg_score,
                    'symbol_sentiments': symbol_sentiment,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Update risk level based on social sentiment
                if abs(avg_score) > 0.7:
                    event.risk_level = "ULTRA_HIGH"
                elif abs(avg_score) > 0.5:
                    event.risk_level = "HIGH"
                    
    except Exception as e:
        print(f"Error enhancing with X sentiment: {e}")
```

### **Step 3: Update Unified Analysis**

Modify `desktop_agent.py`:

```python
def _format_unified_analysis(self, data):
    # ... existing code ...
    
    # Add X sentiment section
    x_sentiment = data.get('x_sentiment', {})
    if x_sentiment and x_sentiment.get('score', 0) != 0:
        score = x_sentiment['score']
        confidence = x_sentiment.get('confidence', 0)
        sentiment = x_sentiment.get('sentiment', 'NEUTRAL')
        
        summary += f"\n🐦 SOCIAL SENTIMENT: {sentiment} ({score:.2f}) - {confidence:.1%} confidence"
        
        if abs(score) > 0.7:
            summary += f"\n⚠️ HIGH SOCIAL IMPACT - Monitor for volatility spikes"
```

---

## 🚀 **Advanced Implementation (Pro Tier)**

### **Real-Time Streaming Service**

Create `infra/x_streaming_service.py`:

```python
class XStreamingService:
    def __init__(self, bearer_token: str):
        self.client = tweepy.StreamingClient(
            bearer_token=bearer_token,
            wait_on_rate_limit=True
        )
        self.symbols = ['BTCUSD', 'EURUSD', 'GBPUSD', 'XAUUSD']
        self.sentiment_buffer = {}
    
    def start_streaming(self):
        """Start real-time sentiment streaming"""
        rules = []
        for symbol in self.symbols:
            rules.append(f"${symbol} OR #{symbol}")
        
        # Add rules for trading keywords
        rules.extend([
            "trading OR forex OR crypto",
            "NFP OR CPI OR FOMC",
            "breakout OR reversal OR trend"
        ])
        
        self.client.add_rules(tweepy.StreamRule(" OR ".join(rules)))
        self.client.filter(
            tweet_fields=['created_at', 'public_metrics', 'author_id'],
            expansions=['author_id']
        )
    
    def on_tweet(self, tweet):
        """Process incoming tweets"""
        # Analyze sentiment in real-time
        # Update sentiment buffer
        # Trigger alerts for significant changes
        pass
```

### **Influencer Monitoring**

```python
class XInfluencerService:
    def __init__(self, bearer_token: str):
        self.client = tweepy.Client(bearer_token=bearer_token)
        self.influencers = {
            'elonmusk': {'weight': 0.9, 'impact': 'HIGH'},
            'naval': {'weight': 0.7, 'impact': 'MEDIUM'},
            'balajis': {'weight': 0.8, 'impact': 'HIGH'}
        }
    
    def monitor_influencers(self, symbol: str):
        """Monitor specific influencers for market impact"""
        for username, config in self.influencers.items():
            tweets = self.client.get_users_tweets(
                username=username,
                max_results=10,
                tweet_fields=['created_at', 'public_metrics']
            )
            
            # Analyze for trading impact
            # Weight their opinions higher
            # Trigger alerts for significant posts
```

---

## 📊 **Integration with Current System**

### **1. Update Environment Variables**

Add to `.env`:
```bash
# X API Configuration
X_BEARER_TOKEN=your_x_bearer_token
X_API_KEY=your_x_api_key
X_API_SECRET=your_x_api_secret
```

### **2. Update Requirements**

Add to `requirements.txt`:
```
tweepy>=4.14.0
```

### **3. Update News Enhancement Script**

Modify `fetch_news_sentiment.py`:

```python
# Add X sentiment enhancement
def enhance_news_with_x_sentiment():
    """Enhance news events with X sentiment"""
    x_service = XSentimentService(
        bearer_token=os.getenv('X_BEARER_TOKEN'),
        openai_api_key=os.getenv('OPENAI_API_KEY')
    )
    
    # Load existing events
    events = load_existing_events()
    
    # Enhance each event
    for event in events:
        if event.impact in ['high', 'ultra']:
            x_service.enhance_with_x_sentiment(event)
    
    # Save enhanced events
    save_events(events)
```

---

## 🎯 **Testing Strategy**

### **Phase 1: Basic Testing (Free Tier)**
```python
# Test script: test_x_sentiment.py
def test_x_sentiment():
    x_service = XSentimentService(
        bearer_token=os.getenv('X_BEARER_TOKEN'),
        openai_api_key=os.getenv('OPENAI_API_KEY')
    )
    
    # Test major symbols
    symbols = ['BTCUSD', 'EURUSD', 'XAUUSD']
    for symbol in symbols:
        sentiment = x_service.get_symbol_sentiment(symbol)
        print(f"{symbol}: {sentiment}")
```

### **Phase 2: Integration Testing**
```python
# Test with news events
def test_news_integration():
    # Load news events
    # Enhance with X sentiment
    # Verify enhanced data structure
    # Test unified analysis output
```

### **Phase 3: Real-Time Testing**
```python
# Test streaming service
def test_streaming():
    # Start streaming service
    # Monitor for sentiment changes
    # Test alert triggers
    # Verify data quality
```

---

## 📈 **Expected Benefits**

### **1. Enhanced News Trading**
- **Pre-news sentiment** before announcements
- **Real-time reactions** during events
- **Post-news sentiment** for market analysis

### **2. Improved Risk Management**
- **Social panic detection** for early warnings
- **Influencer impact** assessment
- **Sentiment shifts** as risk indicators

### **3. Competitive Advantage**
- **Unique data source** not available to all traders
- **Real-time insights** before traditional analysis
- **Social media edge** in fast-moving markets

---

## 🚀 **Implementation Timeline**

### **Week 1: Basic Integration**
- Set up X API service
- Implement basic sentiment analysis
- Test with major symbols

### **Week 2: News Integration**
- Enhance news events with X sentiment
- Update unified analysis
- Test with news trading strategy

### **Week 3: Advanced Features**
- Implement real-time streaming
- Add influencer monitoring
- Test with London Breakout strategy

### **Week 4: Production Ready**
- Full integration testing
- Performance optimization
- Documentation updates

**🎉 X API integration will significantly enhance your MoneyBot's sentiment analysis capabilities! 📈💰**
