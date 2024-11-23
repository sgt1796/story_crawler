# Embedder.py
import numpy as np
import openai
import requests as HTTPRequests ## some packages already have "requests"
from os import getenv
from backoff import on_exception, expo
from scipy.spatial.distance import cosine



from transformers import AutoTokenizer, AutoModel

MAX_TOKENS = 8194

class Embedder:
    def __init__(self, model_name=None, use_api=None, to_cuda=False, attn_implementation=None):
        """
        Initializes the Embedder class, which supports multiple embedding methods, including Jina API, 
        OpenAI API, and local model embeddings.
        
        Args:
            model_name (str): Name of the model to use for embedding.
            use_api (str): Flag to determine whether to use an API for embedding ('jina', 'openai') or a local model (None).
            to_cuda (bool): If True, use GPU; otherwise use CPU. (Some model must run on GPU)
            attn_implementation (str): Attention implementation method for the transformer model.
        """
        self.use_api = use_api
        self.model_name = model_name
        self.to_cuda = to_cuda

        # API-based embedding initialization
        if self.use_api or self.use_api == "":
            supported_apis = ["", 'jina', 'openai',]
            if self.use_api not in supported_apis:
                raise ValueError(f"API type '{self.use_api}' not supported. Supported APIs: {supported_apis}")
            
            elif self.use_api == "": # default
                self.use_api == 'openai'

            elif self.use_api == 'jina':
                pass # maybe add something later

            elif self.use_api == 'openai':
                self.client = openai.Client(api_key=getenv("OPENAI_API_KEY"))
        else:
            # Load PyTorch model for local embedding generation
            if not model_name:
                raise ValueError("Model name must be provided when using a local model.")
            self.attn_implementation = attn_implementation
            self._initialize_local_model()

    def _initialize_local_model(self):
        import torch  # Importing PyTorch only when needed
        import torch.nn.functional as F


        """Initializes the PyTorch model and tokenizer for local embedding generation."""
        if self.attn_implementation:
            self.model = AutoModel.from_pretrained(self.model_name, 
                                                   trust_remote_code=True, 
                                                   attn_implementation=self.attn_implementation, 
                                                   torch_dtype=torch.float16).to('cuda' if self.to_cuda else 'cpu')
        else:
            self.model = AutoModel.from_pretrained(self.model_name, 
                                                   trust_remote_code=True, 
                                                   torch_dtype=torch.float16).to('cuda' if self.to_cuda else 'cpu')
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model.eval()

    def get_embedding(self, texts: list) -> np.ndarray:
        """
        Generates embeddings for a list of texts.
        
        Args:
            texts (list of str): A list of texts to be embedded.
        
        Returns:
            np.ndarray: The embeddings as a numpy array of shape (len(texts), embedding_dim).
        """

        if not isinstance(texts, list):
            raise ValueError("Input must be a list of strings.")

        if self.use_api:
            if self.use_api == 'jina':
                if not self.model_name:
                    self.model_name = "jina-embeddings-v3"
                    print(f"use default model: {self.model_name}")
                return self._get_jina_embedding(texts)
            elif self.use_api == 'openai':
                # set the default to be GPT embedding
                if not self.model_name:
                    self.model_name = "text-embedding-3-small"
                    print(f"use default model: {self.model_name}")
                return self._get_openai_embedding(texts)
            else:
                raise ValueError(f"API type '{self.use_api}' is not supported.")
        else:
            return self._get_torch_embedding(texts)
    
    ## Below are model-specific functions

    @on_exception(expo, HTTPRequests.exceptions.RequestException, max_time=30)
    def _get_jina_embedding(self, texts: list, dim: int = 1024) -> np.ndarray:
        """Fetches embeddings from the Jina API. Requires Jina API key in .env file."""
        # check if dim is between 1 and 1024
        if dim < 1 or dim > 1024:
            raise ValueError("Jina embedding dimension must be between 1 and 1024.")

        url = 'https://api.jina.ai/v1/embeddings'

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {getenv("JINAAI_API_KEY")}'
        }

        input_texts = [text for text in texts]
        data = {
            "model": "jina-embeddings-v3",
            "task": "text-matching",
            "dimensions": 1024,
            "late_chunking": False,
            "embedding_type": "float",
            "input": input_texts
        }
        response = HTTPRequests.post(url, headers=headers, json=data)    

        # Process the response
        if response.status_code == 200:
            # Extract embeddings from the response and convert them to a single NumPy array
            embeddings = response.json().get('data', [])
            embeddings_np = np.array([embedding_data['embedding'] for embedding_data in embeddings], dtype="f")
            return embeddings_np
        elif response.status_code == 429:
            raise HTTPRequests.exceptions.RequestException(
                f"Rate limit exceeded: {response.status_code}, {response.text}"
            )
        
        ## When the input is too long, we need to segment the text
        elif response.status_code == 400:
            ebd = []
            for text in texts:
                chunks = self._Jina_segmenter(text, max_token=MAX_TOKENS)
                token_counts = [len(chunk) for chunk in chunks]
                chunk_embedding = self.get_embedding(chunks)
                weighted_avg = np.average(chunk_embedding, weights=token_counts, axis=0)
                ebd.append(weighted_avg)
            return np.array(ebd, dtype="f")
            
        else:
            print(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Failed to get embedding from Jina API: {response.status_code}, {response.text}")
    
    @on_exception(expo, HTTPRequests.exceptions.RequestException, max_time=30)
    def _get_openai_embedding(self, texts: list) -> np.ndarray:
        """Fetches embeddings from the OpenAI API and returns them as a NumPy array. Requires OpenAI API key in .env file."""
        texts = [text.replace("\n", " ") for text in texts]  # Clean text input
        response = self.client.embeddings.create(input=texts, model=self.model_name)

        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]

        # Convert the list of embeddings to a NumPy array with the desired data type
        return np.array(embeddings, dtype="f")

    def _get_torch_embedding(self, texts: list) -> np.ndarray:
        """Generates embeddings using a local PyTorch model."""
        import torch  # Importing PyTorch only when needed
        import torch.nn.functional as F

        @torch.no_grad()
        def _encode(self, input_texts):
            """
            Generates embeddings for a list of texts using a pytorch local model.
            
            Args:
                input_texts (list of str): A list of texts to encode.
            
            Returns:
                np.ndarray: An array of embeddings.
            """
            batch_dict = self.tokenizer(input_texts, max_length=512, padding=True, truncation=True, return_tensors='pt', return_attention_mask=True).to('cuda' if self.to_cuda else 'cpu')
            
            outputs = self.model(**batch_dict)
            attention_mask = batch_dict["attention_mask"]
            hidden = outputs.last_hidden_state

            reps = _weighted_mean_pooling(hidden, attention_mask)   
            embeddings = F.normalize(reps, p=2, dim=1).detach().cpu().numpy()
            return embeddings
        
        def _weighted_mean_pooling(hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
            """
            Computes weighted mean pooling over the hidden states.
            
            Args:
                hidden (torch.Tensor): The hidden states output from the transformer model.
                attention_mask (torch.Tensor): The attention mask for the input sequences.
            
            Returns:
                torch.Tensor: The pooled representation of the input.
            """
            attention_mask_ = attention_mask * attention_mask.cumsum(dim=1)
            s = torch.sum(hidden * attention_mask_.unsqueeze(-1).float(), dim=1)
            d = attention_mask_.sum(dim=1, keepdim=True).float()
            reps = s / d
            return reps
        
        return _encode(self, texts)
    
    @on_exception(expo, HTTPRequests.exceptions.RequestException, max_time=30)
    def _Jina_segmenter(self, text: str, max_token: int, max_chunk = None, merge_precision = 128) -> list[str]:
        """
        Segments a given text into chunks using the Jina API, they merge the chunks based on semantic similarity to max_chunk number of chunks.

        Args:
            text (str): The text to be segmented.
            max_token (int): The maximum number of tokens allowed in each chunk.
            max_chunk (int | None, optional): The maximum number of chunks to generate. Defaults to None.
            merge_precision (int, optional): The precision used for merging chunks, only need if merge chunks. Defaults to 128.

        Returns:
            list[str]: A list of segmented chunks.

        Raises:
            HTTPRequests.exceptions.RequestException: If there is an error in the API request.

        Note:
            This function requires a Jina API key in the .env file.
        """
        url = 'https://segment.jina.ai/'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {getenv("JINAAI_API_KEY")}'
        }
        data = {
            "content": text,
            "return_tokens": True,
            "return_chunks": True,
            "max_chunk_length": max_token
        }
        response = HTTPRequests.post(url, headers=headers, json=data)
        chunks = response.json().get('chunks', [])
        if max_chunk is not None and len(chunks) >= max_chunk:
            chunks = self._iterative_sequential_merge(chunks, max_chunk, merge_precision)
        return chunks
    
    def _iterative_sequential_merge(self, chunked_text, target_count, embedding_dim):
        """
        Iteratively merge sequentially adjacent text chunks based on semantic similarity
        until a target count is reached.

        Args:
            text_list (list of str): List of textual elements to merge.
            embedder: Embedder object with a method `_get_jina_embedding(chunked_text, dim)`.
            target_count (int): Desired number of elements in the final list.
            embedding_dim (int): Dimension of the embeddings.

        Returns:
            list of str: Merged list of text elements.
        """
        text_chunks = chunked_text.copy() # create a copy of the text chunks so that the original list is not modified
        print(f"Initial number of chunks: {len(text_chunks)}")
        print(f"Target number of chunks: {target_count}")
        ## Check if the target count is already reached
        if len(text_chunks) <= target_count:
            return text_chunks
        
        chunk_embedding = self._get_jina_embedding(text_chunks, dim = embedding_dim)
        # list of similarity of adjacent chunks
        similarities = [
            1 - cosine(chunk_embedding[i], chunk_embedding[i + 1])
            for i in range(len(chunk_embedding) - 1)
        ]
        while len(text_chunks) > target_count:
            ## Find the most similar adjacent chunks, merge them and remove the second chunk
            ## Then update the similarity scores
            max_idx = np.argmax(similarities)
            print(f"Merge chunk {max_idx} and {max_idx+1} with a similarity score of {np.max(similarities)}. New length: {len(text_chunks)}")    

            merged_text = f"{chunked_text[max_idx]} {chunked_text[max_idx + 1]}"
            text_chunks[max_idx] = merged_text
            text_chunks.pop(max_idx + 1)
            #print(merged_text)

            ## update embedding
            chunk_embedding[max_idx] = self._get_jina_embedding([merged_text], dim = embedding_dim)[0]
            chunk_embedding = np.delete(chunk_embedding, max_idx + 1, axis=0)

            # Update similarities
            if max_idx > 0:  # Update similarity with the previous neighbor
                similarities[max_idx - 1] = 1 - cosine(chunk_embedding[max_idx - 1], chunk_embedding[max_idx])
            if max_idx < len(similarities) - 1:  # Update similarity with the next neighbor
                similarities[max_idx] = 1 - cosine(chunk_embedding[max_idx], chunk_embedding[max_idx + 1])
            # Remove the similarity for the merged element
            similarities.pop(max_idx)

        return text_chunks
