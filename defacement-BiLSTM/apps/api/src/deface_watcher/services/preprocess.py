from tensorflow.keras.preprocessing.sequence import pad_sequences


def preprocess_text(text, tokenizer, max_length: int):
    sequence = tokenizer.texts_to_sequences([text])
    return pad_sequences(sequence, maxlen=max_length, padding="post", truncating="post")
