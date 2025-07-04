import torch

from torch import nn

from torch.nn import BCEWithLogitsLoss
import torch.nn.functional as F


class PO2GO(nn.Module):
    def __init__(self,
                 terms_emb,
                 protein_dim=1280,
                 latent_dim=768,
                 prob_predict_temp_dim=1280,
                 num_heads=8):
        super().__init__()
        self.terms_emb = terms_emb
        self.nb_classes = terms_emb.shape[0]
        self.latent_dim = latent_dim
        self.term_dim = terms_emb.shape[1]
        self.protein_dim = protein_dim

        # protein projector
        self.q = self.init_predictor(self.protein_dim,
                                     self.latent_dim, 1024, 1024, 0.2)
        # 多头自注意力层
        self.attention = nn.MultiheadAttention(embed_dim=latent_dim, num_heads=num_heads)

        # term projector
        self.k = nn.Linear(self.term_dim, self.latent_dim)
        # probability predictor
        self.fc = nn.Linear(self.nb_classes, prob_predict_temp_dim)
        self.fc2 = nn.Linear(prob_predict_temp_dim, self.nb_classes)

    def init_predictor(self, in_dim, out_dim, temp_dim=1024, norm_dim=1024, drop=0.2):
        return nn.Sequential(
            nn.Linear(in_dim, temp_dim),
            nn.BatchNorm1d(norm_dim),
            nn.ReLU(),
            nn.Dropout(drop),
            nn.Linear(temp_dim, out_dim),
        )

    def forward(self, embeddings, labels=None):
        # 投影蛋白质特征
        x = self.q(embeddings)  # [B, latent_dim]

        # 多头自注意力
        x = x.unsqueeze(0)  # [1, B, latent_dim]
        attn_output, _ = self.attention(x, x, x)
        x = attn_output.squeeze(0)  # [B, latent_dim]

        # 投影 GO 术语特征
        y = self.k(self.terms_emb)  # [nb_classes, latent_dim]

        # 计算相似度
        x = torch.matmul(x, y.T)  # [B, nb_classes]

        # 概率预测
        x = self.fc(x)
        x = F.relu(x)
        x = F.dropout(x, 0.2)
        logits = self.fc2(x)
        outputs = (logits,)
        if labels is not None:
            loss_fct = BCEWithLogitsLoss()
            labels = labels.float()
            loss = loss_fct(logits.view(-1, self.nb_classes),
                            labels.view(-1, self.nb_classes))
            outputs = (loss, logits)
        return outputs


if __name__ == '__main__':
    node_embedding = torch.rand((10000, 200))
    protein_embedding = torch.rand((4, 1280))
    label = torch.zeros((4, 10000))
    model = PO2GO(terms_emb=node_embedding,
                  protein_dim=1280,
                  latent_dim=768,
                  prob_predict_temp_dim=1280,
                  num_heads=8 )
    print(model)
    outs = model(protein_embedding, label)
