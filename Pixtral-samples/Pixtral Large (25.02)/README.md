# Math Problem Assistant with Pixtral Large on AWS

This demo showcases a Math Problem Assistant powered by the Pixtral Large model on AWS Bedrock. The application helps students understand and solve math problems by analyzing images of math questions and providing step-by-step guidance.

## Prerequisites

- Python 3.11 or later
- AWS account with access to Bedrock service
- AWS credentials configured locally
- Access to the Mistral Pixtral Large model on AWS Bedrock

## Quick Start

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your AWS credentials:
   - Create a `.env` file in the project directory
   - Add your AWS configuration:
     ```
     AWS_ACCESS_KEY_ID=your_access_key
     AWS_SECRET_ACCESS_KEY=your_secret_key
     AWS_DEFAULT_REGION=your_region
     ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

5. Open your browser and navigate to http://localhost:8501

## Usage

1. Click the "Try Demo" button to test the app with a pre-loaded vector geometry problem, or
2. Enter the URL of any math problem image in the input field
3. The app will analyze the image and provide:
   - A simple explanation of what the problem is asking
   - Identification of key mathematical concepts
   - Step-by-step guidance for solving the problem
   - Hints for challenging aspects
4. Use the chat interface for follow-up questions about the problem

## Notes

- The app uses LaTeX for mathematical notation, rendered through MathJax
- The model is designed to guide students through the problem-solving process rather than providing direct answers
- Image URLs must be publicly accessible 