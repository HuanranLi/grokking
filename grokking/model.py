from einops import rearrange, repeat
import torch
from torch import nn, Tensor
import itertools

class DecoderBlock(torch.nn.Module):
  def __init__(self, dim_model: int, n_heads: int):
    super().__init__()

    self.self_attn = nn.MultiheadAttention(dim_model, n_heads)
    self.self_attn_norm = nn.LayerNorm(dim_model)
    self.ffn = nn.Sequential(
        nn.Linear(dim_model, dim_model * 4),
        nn.GELU(),
        nn.Linear(dim_model * 4, dim_model)
    )
    self.ffn_norm = nn.LayerNorm(dim_model)

  def forward(self, x: Tensor):
    attn_mask = torch.full(
        (len(x), len(x)), -float("Inf"), device=x.device, dtype=x.dtype
    )
    attn_mask = torch.triu(attn_mask, diagonal=1)

    a1, _ = self.self_attn(x, x, x, attn_mask=attn_mask)
    a1 = self.self_attn_norm (x + a1)
    a2 = self.ffn(a1)
    a2 = self.ffn_norm(a1 + a2)

    return a2

def generate_all_combinations(n_columns):
    all_combinations = []
    for r in range(1, n_columns + 1):  # Start from 1 to include at least one column
        combinations = list(itertools.combinations(range(n_columns), r))
        all_combinations.extend(combinations)

    return all_combinations

class Transformer(torch.nn.Module):
  def __init__(self, num_layers: int, dim_model: int, num_heads: int, num_tokens: int, seq_len: int):
    super().__init__()

    self.token_embeddings = nn.Embedding(num_tokens, dim_model)
    self.position_embeddings = nn.Embedding(seq_len, dim_model)
    self.model = nn.Sequential(
        *[DecoderBlock(dim_model, num_heads) for _ in range(num_layers)],
        nn.LayerNorm(dim_model),
        nn.Linear(dim_model, num_tokens)
    )

    self.noise_cols_comb = generate_all_combinations(4)


  def forward(self, inputs: Tensor, noise_level = 0, noise_cols_mode = 0):
    batch_size, context_len = inputs.shape

    token_embedding = self.token_embeddings(inputs)

    positions = repeat(torch.arange(context_len, device=inputs.device), "p -> b p", b = batch_size)
    position_embedding = self.position_embeddings(positions)

    embedding = token_embedding + position_embedding

    embedding = rearrange(embedding, 'b s d -> s b d')

    if noise_level > 0:
        noise_cols = self.noise_cols_comb[noise_cols_mode]
        # [S, B, D]
        noise = torch.randn_like(embedding) * noise_level

        embedding[noise_cols] += noise[noise_cols]

    return self.model(embedding)
