# Load model directly
from transformers import AutoTokenizer, AutoModel

tokenizer = AutoTokenizer.from_pretrained("jcblaise/roberta-tagalog-large")
model = AutoModel.from_pretrained("jcblaise/roberta-tagalog-large")

# Input text
text = "Ang panahon ngayon ay mainit, walang ulan at maaraw."

# Tokenize and encode text using batch_encode_plus
# The function returns a dictionary containing the token IDs and attention masks
encoding = tokenizer.batch_encode_plus(
    [text],  # List of input texts
    padding=True,  # Pad to the maximum sequence length
    truncation=True,  # Truncate to the maximum sequence length if necessary
    return_tensors="pt",  # Return PyTorch tensors
    add_special_tokens=True,  # Add special tokens CLS and SEP
)

input_ids = encoding["input_ids"]  # Token IDs
# print input IDs
print(f"Input ID: {input_ids}")
attention_mask = encoding["attention_mask"]  # Attention mask
# print attention mask
print(f"Attention mask: {attention_mask}")

import torch

# Generate embeddings using RoBERTa model
with torch.no_grad():
    outputs = model(input_ids)
    word_embeddings = outputs.last_hidden_state  # This contains the embeddings

# Output the shape of word embeddings
print(f"Shape of Word Embeddings: {word_embeddings.shape}")


# Decode the token IDs back to text
decoded_text = tokenizer.decode(input_ids[0], skip_special_tokens=True)
# print decoded text
print(f"Decoded Text: {decoded_text}")
# Tokenize the text again for reference
tokenized_text = tokenizer.tokenize(decoded_text)
# print tokenized text
print(f"tokenized Text: {tokenized_text}")
# Encode the text
encoded_text = tokenizer.encode(text, return_tensors="pt")  # Returns a tensor
# Print encoded text
print(f"Encoded Text: {encoded_text}")


for token, embedding in zip(tokenized_text, word_embeddings[0]):
    # print(f"Token: {token}")
    print(f"Embedding: {embedding}")
