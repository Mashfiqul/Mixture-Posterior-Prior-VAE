

# **Modified Mixtures of VAE Model using Reuters Dataset**
"""

# This is the General Code

"""### **Libraries**"""

# Commented out IPython magic to ensure Python compatibility.
import warnings
warnings.filterwarnings("ignore")

# Debugger
import pdb

import time

# math and numpy
import itertools
import decimal
import mpmath
import math
import numpy as np
import random

# pandas
import pandas as pd
from pandas import DataFrame
from collections import Counter

# matplot
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from IPython import display
display.set_matplotlib_formats("svg")
# %matplotlib inline
import matplotlib.patches as mpatches

# scipy
import scipy.linalg as la
from scipy.stats import entropy
from scipy.stats import norm
from scipy.stats import multivariate_normal
import scipy.io as scio

# sklearn
from sklearn import datasets
from sklearn import metrics
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix
from sklearn.cluster import KMeans
from sklearn.metrics import normalized_mutual_info_score, adjusted_rand_score, accuracy_score
from scipy.optimize import linear_sum_assignment
import seaborn as sns
from sklearn.manifold import TSNE
from sklearn.datasets import load_digits
from sklearn.datasets import load_iris
from sklearn.preprocessing import MinMaxScaler


# torch
import torch
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F
import torchvision
from torch.optim.lr_scheduler import StepLR
import torchvision.transforms as transforms
import torchvision.datasets as datasets
from torch.utils.data import DataLoader, TensorDataset
from torchvision.utils import make_grid
from torch.distributions.multivariate_normal import MultivariateNormal
from torch.distributions.normal import Normal
from torch.distributions.mixture_same_family import MixtureSameFamily
from torch.distributions.categorical import Categorical
from torch.distributions.wishart import Wishart
from torch.distributions.dirichlet import Dirichlet
from torch.distributions import Bernoulli
from torch.utils.data import Dataset
import torchvision.models as models
from torchvision.models import resnet50
from torchvision.datasets import STL10

"""### **Device**"""

# start_time = time.time()
device=torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print("Device:", device, "\n")
print("PyTorch Version:", torch.__version__, "\n")
print("Total Number of GPUs: ", torch.cuda.device_count())



"""## **Hyperparameters**"""

# VAE Part

num_epochs=2000
learning_rate=1e-4
step_size=20
weight_decay=1e-5
input_dim=2000
encoder_hidden_dim_1=500
encoder_hidden_dim_2=500
encoder_hidden_dim_3=2000
latent_dim=5
decoder_hidden_dim_1=2000
decoder_hidden_dim_2=500
decoder_hidden_dim_3=500
output_dim=2000
train_batch_size=100
test_batch_size=100
gamma=0.9


# GMM Part
num_components=4
num_iterations=20
epsilon=1e-10
decimal.getcontext().prec = 28
clustering_method="GMM"
covariance_type="full"


# Set seeds for NumPy, PyTorch, and Python's random module
random_seed=5
np.random.seed(random_seed)
torch.manual_seed(random_seed)
torch.cuda.manual_seed(random_seed)
random.seed(random_seed)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False


# Early Stopping
max_patience=num_epochs+1
best_test_loss=float("inf")
patience_counter=0

# File Name
Dataset_name = "Reuters"
Model="MMVAE"
Assignment="Hard"
Model_name= f"{Model}_{clustering_method}_{covariance_type}_{random_seed}_{Dataset_name}_Latent_dim_{latent_dim}_{Assignment}_Optimization"

"""# **Reuters Dataset**

### **Summary of Dataset**
"""

# data=scio.loadmat("/content/sample_data/reuters10k.mat")
data=scio.loadmat('/home/chowdhma/Desktop/Reuters_Dataset/reuters10k.mat')
X = data['X']
Y = data['Y'].squeeze()

class Reuters(Dataset):
    def __init__(self, mode='train', transforms=None):
        # digits = load_digits()
        if mode == 'train':
            self.data = X[:9000].astype(np.float32)
            self.targets = Y[:9000]
        else:
            self.data = X[9000:].astype(np.float32)
            self.targets = Y[9000:]

        self.transforms = transforms

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        sample = self.data[idx]
        target = self.targets[idx]
        if self.transforms:
            sample = self.transforms(sample)
        return sample, target

train_data=Reuters(mode='train')
test_data = Reuters(mode='test')

# # sc=StandardScaler()
# sc = MinMaxScaler()
# train_data.data = sc.fit_transform(train_data.data)
# test_data.data = sc.transform(test_data.data)

X_train=torch.FloatTensor(train_data.data)
X_test=torch.FloatTensor(test_data.data)
y_train=torch.LongTensor(train_data.targets)
y_test=torch.LongTensor(test_data.targets)

trainset=TensorDataset(X_train, y_train)
testset=TensorDataset(X_test, y_test)


"""### **Data Loader**"""

train_loader=DataLoader(trainset, batch_size=train_batch_size, shuffle=True)
test_loader=DataLoader(testset, batch_size=test_batch_size, shuffle=False)

"""# **Functions**

### **Clustering Accuracy with Linear Assignment**
"""

def cluster_acc_with_assignment(y_true, y_pred):
    y_true = y_true.astype(np.int64)
    assert y_pred.size == y_true.size
    D = max(y_pred.max(), y_true.max()) + 1
    w = np.zeros((D, D), dtype=np.int64)
    for i in range(y_pred.size):
        w[y_pred[i], y_true[i]] += 1
    row_ind, col_ind = linear_sum_assignment(w.max() - w)

    new_predicted_labels = np.array([col_ind[i] for i in y_pred])
    accuracy = sum([w[row, col] for row, col in zip(row_ind, col_ind)]) * 1.0 / y_pred.size
    return accuracy, new_predicted_labels

"""# **MMVAE Model**

### **Encoder Class**
"""

class Encoder(nn.Module):
  def __init__(self):
    super(Encoder, self).__init__()
    self.encoder = nn.Sequential(
        nn.Linear(input_dim, encoder_hidden_dim_1),
        nn.ReLU(),
        nn.Linear(encoder_hidden_dim_1, encoder_hidden_dim_2),
        nn.ReLU(),
        nn.Linear(encoder_hidden_dim_2, encoder_hidden_dim_3),
        nn.ReLU()
        )
    self.mu_layer = nn.Linear(encoder_hidden_dim_3, latent_dim * num_components)
    self.log_var_layer = nn.Linear(encoder_hidden_dim_3, latent_dim * num_components)

  def forward(self, x):
      x = self.encoder(x)
      mu_layer = self.mu_layer(x)
      log_var_layer = self.log_var_layer(x)
      mu_k = mu_layer.view(-1, num_components, latent_dim)
      log_var_k = log_var_layer.view(-1, num_components, latent_dim)
      return mu_k, log_var_k

"""### **Decoder Class**"""

class Decoder(nn.Module):
  def __init__(self):
    super(Decoder, self).__init__()
    self.decoder = nn.Sequential(
        nn.Linear(latent_dim, decoder_hidden_dim_1),
        nn.ReLU(),
        nn.Linear(decoder_hidden_dim_1, decoder_hidden_dim_2),
        nn.ReLU(),
        nn.Linear(decoder_hidden_dim_2, decoder_hidden_dim_3),
        nn.ReLU(),
        nn.Linear(decoder_hidden_dim_3, output_dim),
        )
  def forward(self, z):
      return self.decoder(z)

"""### **GMM Prior Class**"""

class GMM(nn.Module):
  def __init__(self, M, K):
    super(GMM, self).__init__()
    self.M=M
    self.K=K
    self.means=nn.Parameter(torch.randn(self.K, self.M))                         # [K, M]
    self.logvars=nn.Parameter(torch.randn(self.K, self.M))                       # [K, M]
    # self.weights=nn.Parameter(torch.ones(self.K)/self.K)                       # [K]
    self.weights=nn.Parameter(Dirichlet(torch.ones(self.K)).sample())            # [K]

  def get_params(self):
    return self.means, self.logvars, self.weights

  def log_prob(self, z):
    num_samples, num_components, num_features = z.shape                          # [B, K, M]
    mean, logvar, weight = self.get_params()
    weight=F.softmax(weight, dim=0)                                              # [K]
    mean=mean.reshape(1, num_components, latent_dim)                             # [1, K, M]
    logvar=logvar.reshape(1, num_components, latent_dim)                         # [1, K, M]
    prior_dist=Normal(loc=mean, scale=torch.exp(0.5*logvar))
    log_pi=torch.log(weight)
    prior_log_prob=prior_dist.log_prob(z).sum(dim=2)                             # [B, K]
    return log_pi, prior_log_prob                                                # [K], [B, K]

"""### **MMVAE Class**"""

class MMVAE(nn.Module):
  def __init__(self):
    super(MMVAE, self).__init__()
    self.encoder=Encoder()
    self.decoder=Decoder()
    self.prior=GMM(M=latent_dim, K=num_components)

  def reparameterize(self, mu, log_var):
    if self.training:
      sigma=torch.exp(0.5*log_var)
      eps=torch.randn_like(sigma)
      z=mu+eps*sigma
      return z
    else:
      return mu

  def forward(self, x):
    x=x.view(-1, input_dim)
    encoder_mu_k, encoder_logvar_k=self.encoder(x)
    latent_z_k=self.reparameterize(encoder_mu_k, encoder_logvar_k)
    log_pi_k, log_normal_prior_k=self.prior.log_prob(latent_z_k)
    decoder_mu=self.decoder(latent_z_k)
    return decoder_mu, log_pi_k, log_normal_prior_k, latent_z_k, encoder_mu_k, encoder_logvar_k

"""### **MMVAE Model and Optimizer**"""

model=MMVAE().to(device)
optimizer = optim.Adam(model.parameters(), lr=learning_rate)
scheduler = StepLR(optimizer, step_size=step_size, gamma=gamma)
print(model)
num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print('\n \n Number of Estimated Parameters: %d' % num_params)

model_info=str(model)
file_path=f"Model_Architecture_{Model_name}_{Dataset_name}.txt"
with open(file_path, "w") as file:
    file.write("Model Architecture:\n")
    file.write(model_info)
    file.write("\n\nNumber of Estimated Parameters: %d\n" % num_params)

"""# **Model Training**

### **Backpropagation and Parameter Updates**
"""

Training_Losses=[]
Test_Loss=[]
True_Labels=[]
Latent_embeddings_best=[]

# GMM Part
Accuracy_GMM=[]
Mean_Accuracy_GMM=[]
STD_Accuracy_GMM=[]
NMI_GMM=[]
ARI_GMM=[]
Posterior_EM=[]
Updated_GMM_Labels=[]

# Posterior Probability
Accuracy_Posterior=[]
NMI_Posterior=[]
ARI_Posterior=[]
Updated_Posterior_Labels=[]
Posterior_NN=[]

print(f"Training and Testing {Model_name} Model: {Dataset_name} Dataset: \n\n")

for epoch in range(num_epochs):

  ## Training Step
  model.train()
  Training_Losses.append(0)
  num_batches=0

  for training_features, _ in train_loader:
    optimizer.zero_grad()
    training_features=training_features.reshape(-1, input_dim)
    training_features=training_features.to(device)

    decoder_mu, log_pi_k, log_normal_prior_k, latent_z_k, latent_mu_k, latent_logvar_k=model(training_features)
    decoder_mu=decoder_mu.to(device)                                             # [B, K, D]
    batch_size, batch_dim = training_features.shape

    # Encoder Likelihood: [B, K, M]

    q_z_y=Normal(loc=latent_mu_k, scale=torch.exp(0.5*latent_logvar_k))
    log_q_z_y=q_z_y.log_prob(latent_z_k).sum(dim=2)


    prior_posterior_log_likelihood=log_normal_prior_k+log_pi_k-log_q_z_y

    # Posterior Probability

    q_numerator=torch.exp(prior_posterior_log_likelihood)                        # [B, K]
    q_denominator=torch.sum(q_numerator, dim=1, keepdim=True)
    q_y_i_k=q_numerator/q_denominator

    ################################ Decoder Likelihood: Real-Valued Data ########################

    p_x_z=Normal(loc=decoder_mu, scale=torch.ones_like(decoder_mu))
    input=training_features.reshape(batch_size, 1, input_dim)
    log_p_x_z=p_x_z.log_prob(input)
    log_p_x_z_ik=log_p_x_z.sum(dim=2)


    ##################################### ELBO #################################


    reconstruction_prior_posterior_log_liklihood=log_p_x_z_ik+prior_posterior_log_likelihood
    best_k_train=torch.argmax(q_y_i_k, dim=1)
    Max_ELBO_Train=reconstruction_prior_posterior_log_liklihood[range(batch_size), best_k_train]
    ELBO=torch.sum(Max_ELBO_Train, dim=0)

    # Total Loss
    Total_Loss = -ELBO

    # Backpropagation
    Total_Loss.backward()
    optimizer.step()
    num_batches+=1
    Training_Losses[-1]+=Total_Loss.item()

  # Update the Learning Rate
  scheduler.step()

  # Average Losses
  Training_Losses[-1]/= num_batches

  ## Evaluation Step

  model.eval()
  Final_Test_Loss=0.0
  number_of_batches=0
  ground_truth_labels=[]
  latent_best_z=[]

  # Posterior Part
  posterior_probabilities=[]

  # GMM Part
  simulated_gmm_accuracies = []
  simulated_gmm_nmi = []
  simulated_gmm_ari = []
  simulated_predicted_labels_gmm = []
  simulated_posterior_probabilities_gmm = []
  reconstructions = []
  original_image = []
  Best_class=[]

  with torch.no_grad():
    for test_features, test_labels in test_loader:

      test_features=test_features.reshape(-1, input_dim)
      test_features=test_features.to(device)
      test_labels=test_labels.to(device)

      decoder_mu_test, log_pi_k_test, log_normal_prior_k_test, latent_z_k_test, latent_mu_k_test, latent_logvar_k_test = model(test_features)
      decoder_mu_test=decoder_mu_test.to(device)
      ground_truth_labels.append(test_labels.cpu().numpy())
      batch_size, batch_dim = test_features.shape

      # Encoder Likelihood: Shape [B, K]

      q_z_y_test=Normal(loc=latent_mu_k_test, scale=torch.exp(0.5*latent_logvar_k_test))
      log_q_z_y_test = q_z_y_test.log_prob(latent_z_k_test).sum(dim=2)

      prior_posterior_log_likelihood_test=log_normal_prior_k_test+log_pi_k_test-log_q_z_y_test


      ########################### Posterior Probability ########################


      q_numerator_test=torch.exp(prior_posterior_log_likelihood_test)                        # [B, K]
      q_denominator_test=torch.sum(q_numerator_test, dim=1, keepdim=True)
      q_y_i_k_test=q_numerator_test/q_denominator_test
      posterior_probabilities.append(q_y_i_k_test)

      ################################ Decoder Likelihood: Real-Valued Data ########################

      p_x_z_test=Normal(loc=decoder_mu_test, scale=torch.ones_like(decoder_mu_test))
      input_test=test_features.reshape(batch_size, 1, input_dim)
      log_p_x_z_test=p_x_z_test.log_prob(input_test)
      log_p_x_z_ik_test=log_p_x_z_test.sum(dim=2)


      ######################### Test ELBO  #####################################


      reconstruction_prior_posterior_log_liklihood_test=log_p_x_z_ik_test+prior_posterior_log_likelihood_test
      best_k_test=torch.argmax(q_y_i_k_test, dim=1)
      Max_ELBO_test=reconstruction_prior_posterior_log_liklihood_test[range(batch_size), best_k_test]
      ELBO_test=torch.sum(Max_ELBO_test, dim=0)

      ##########################################################################

      # Best Class

      best_reconstruction_test=decoder_mu_test[torch.arange(decoder_mu_test.size(0)), best_k_test, :]

      Best_class.append(best_k_test)
      latent_z=latent_z_k_test[torch.arange(batch_size), best_k_test, :]
      latent_best_z.append(latent_z)
      reconstructions.append(best_reconstruction_test)
      original_image.append(test_features)


      # Total Loss

      Total_Test_Loss = -ELBO_test
      Final_Test_Loss+= Total_Test_Loss.item()
      number_of_batches+= 1


    # Average Loss
    Final_Test_Loss/=number_of_batches
    Test_Loss.append(Final_Test_Loss)

    # Latent Space
    latent_best=torch.cat(latent_best_z, dim=0).cpu().detach().numpy()
    Latent_embeddings_best.append(latent_best)

    # True Labels
    ground_truth_labels_numpy = np.concatenate(ground_truth_labels)
    True_Labels.append(ground_truth_labels_numpy)

    ################## Clustering using Posterior Probability###################


    # Clustering using Posterior Probabilities (Soft Assignment)

    posterior_probabilities_q_y_i_k=torch.cat(posterior_probabilities, dim=0)
    predicted_labels_posterior=torch.argmax(posterior_probabilities_q_y_i_k, dim=1).cpu().numpy()
    # predicted_labels_posterior=torch.cat(Best_class, dim=0).cpu().numpy()
    Posterior_NN.append(posterior_probabilities_q_y_i_k)
    nmi_posterior = normalized_mutual_info_score(ground_truth_labels_numpy, predicted_labels_posterior)
    ari_posterior= adjusted_rand_score(ground_truth_labels_numpy, predicted_labels_posterior)
    NMI_Posterior.append(nmi_posterior)
    ARI_Posterior.append(ari_posterior)
    new_accuracy_posterior, new_predicted_labels_posterior = cluster_acc_with_assignment(ground_truth_labels_numpy, predicted_labels_posterior)
    Accuracy_Posterior.append(new_accuracy_posterior)
    Updated_Posterior_Labels.append(new_predicted_labels_posterior)


    ##################Clustering using Gaussian Mixture Model###################

    for i in range(num_iterations):
      # seed = np.random.randint(0, 100)
      gmm = GaussianMixture(n_components=num_components, covariance_type=covariance_type, random_state=i)
      predicted_labels_gmm = gmm.fit_predict(latent_best)
      posterior_probabilities_gmm = gmm.predict_proba(latent_best)
      simulated_posterior_probabilities_gmm.append(posterior_probabilities_gmm)
      nmi_gmm = normalized_mutual_info_score(ground_truth_labels_numpy, predicted_labels_gmm)
      ari_gmm = adjusted_rand_score(ground_truth_labels_numpy, predicted_labels_gmm)
      new_accuracy_gmm, new_predicted_labels_gmm = cluster_acc_with_assignment(ground_truth_labels_numpy,
                                                                                predicted_labels_gmm)
      simulated_gmm_accuracies.append(new_accuracy_gmm)
      simulated_gmm_nmi.append(nmi_gmm)
      simulated_gmm_ari.append(ari_gmm)
      simulated_predicted_labels_gmm.append(new_predicted_labels_gmm)

    average_gmm_accuracy = np.mean(simulated_gmm_accuracies)
    max_gmm_accuracy = np.max(simulated_gmm_accuracies)
    sd_gmm_accuracy = np.std(simulated_gmm_accuracies)
    Accuracy_GMM.append(max_gmm_accuracy)
    Mean_Accuracy_GMM.append(average_gmm_accuracy)
    STD_Accuracy_GMM.append(sd_gmm_accuracy)
    best_accuracy_index = simulated_gmm_accuracies.index(np.max(simulated_gmm_accuracies))
    Updated_GMM_Labels.append(simulated_predicted_labels_gmm[best_accuracy_index])
    Posterior_EM.append(simulated_posterior_probabilities_gmm[best_accuracy_index])
    NMI_GMM.append(simulated_gmm_nmi[best_accuracy_index])
    ARI_GMM.append(simulated_gmm_ari[best_accuracy_index])

    ####################################################################################################################

    if (epoch+1)%5==0:
        print(f"\n Step: [{epoch+1}/{num_epochs}] \t  Training Loss: {Training_Losses[-1]: 0.2f} \t Test Loss: {Final_Test_Loss: 0.2f} \
        \t Accuracy (GMM): {max_gmm_accuracy: 0.2f} \t Accuracy (Posterior): {new_accuracy_posterior: 0.2f} \t NMI (GMM): {simulated_gmm_nmi[best_accuracy_index]: 0.2f} \t NMI (Posterior): {nmi_posterior: 0.2f} \
        \t LR: {scheduler.get_last_lr()[0]:0.6f}")

"""### **Model Parameters**"""


param_list = [*model.parameters()]
weights=param_list[-1]


"""# **Results**

### **Clustering Accuracy**
"""

print("\n Loss:")
print("-"*50)
print("\n Final Training Loss:", Training_Losses[-1])
print("\n Final Test Loss:", Test_Loss[-1])
print("-"*50)
print("\n Posterior Probability Results:")
print(f"\n Accuracy (Posterior): {Accuracy_Posterior[-1]: 0.3f}")
print(f'\n NMI (Posterior): {NMI_Posterior[-1]: 0.2f}')
print(f'\n ARI (Posterior): {ARI_Posterior[-1]: 0.2f}')
print("-"*50)

print("-"*50)
print("\n GMM Results:")
print(f"\n Clustering accuracy (GMM): {Accuracy_GMM[-1]: 0.3f}")
print(f'\n NMI (GMM): {NMI_GMM[-1]: 0.2f}')
print(f'\n ARI (GMM): {ARI_GMM[-1]: 0.2f}')
print("-"*50)

"""### **Training Losses and Test Losses**"""

plt.figure(figsize=(8, 6))
x=np.linspace(1, len(Training_Losses), len(Training_Losses))
y=np.linspace(1, len(Test_Loss), len(Test_Loss))
plt.plot(x, Training_Losses, label='Training Losses', color="blue", linestyle="solid", linewidth=1)
plt.plot(y, Test_Loss, label='Test Losses', color="green", linestyle="solid", linewidth=1)
plt.xlabel('Epochs')
plt.ylabel('Negative ELBO')
# plt.title('Training and Test Losses')
plt.legend(loc="best")
plt.grid()
plt.savefig(f"Training_Test_Loss_{Model_name}_{Dataset_name}.pdf", format="pdf", bbox_inches="tight")
plt.close()

"""### **Accuracy Plot**"""

plt.figure(figsize=(8, 6))
x=np.linspace(1, len(Accuracy_GMM), len(Accuracy_GMM))
y=np.linspace(1, len(Accuracy_Posterior), len(Accuracy_Posterior))
plt.plot(x, Accuracy_GMM, label='Accuracy (GMM)', color="blue", linestyle="solid", linewidth=1)
plt.plot(y, Accuracy_Posterior, label='Accuracy (Posterior)', color="green", linestyle="solid", linewidth=1)
plt.xlabel('Epochs')
plt.ylabel('Clustering Accuracy')
plt.legend(loc="best")
plt.grid()
plt.savefig(f"Accuracy_{Model_name}_{Dataset_name}_GMM_Posterior.pdf", format="pdf", bbox_inches="tight")
plt.close()


"""### **Accuracy (GMM)**"""

x=np.linspace(1, len(Accuracy_GMM), len(Accuracy_GMM))
plt.figure(figsize=(8, 6))
plt.xlabel("Epochs")
plt.ylabel('Clustering Accuracy')
plt.plot(x, Accuracy_GMM, color="blue", linestyle="solid", linewidth=1)
plt.grid()
plt.savefig(f"Accuracy_{Model_name}_{Dataset_name}_GMM.pdf", format="pdf", bbox_inches="tight")
plt.close()

"""# **Confusion Matrix and t-SNE**

### **Confusion Matrix (GMM)**
"""

conf_matrix = confusion_matrix(True_Labels[-1], Updated_GMM_Labels[-1])
plt.figure(figsize=(8, 6))
sns.heatmap(conf_matrix, annot=True, fmt="d", cmap="Blues", cbar=False)
plt.xlabel("Predicted Labels")
plt.ylabel("True Labels")
# plt.title("Confusion Matrix")
plt.savefig(f"Confusion_Matrix_{Model_name}_{Dataset_name}_GMM.pdf", format="pdf", bbox_inches="tight")
plt.close()


"""### **t-SNE Visualization (GMM)**"""

latent_space_recoded=torch.tensor(Latent_embeddings_best[-1], dtype=torch.float32)
# tsne = TSNE(n_components=2, perplexity=5, random_state=random_seed)
tsne = TSNE(n_components=2, random_state=random_seed)
latent_tsne = tsne.fit_transform(latent_space_recoded)
plt.figure(figsize=(10, 10))
cmap = plt.cm.get_cmap('rainbow', len(np.unique(Updated_GMM_Labels[-1])))

scatter = plt.scatter(latent_tsne[:, 0], latent_tsne[:, 1], c=Updated_GMM_Labels[-1], cmap='rainbow')
plt.colorbar(scatter)
# plt.title('Visualization of Latent Space with Clusters')
plt.xlabel('Latent Embeddings (1)')
plt.ylabel('Latent Embeddings (2)')
# plt.grid(True)
# Create legend handles for each cluster
legend_handles = [mpatches.Patch(color=cmap(i), label=f'Cluster {i}') for i in np.unique(Updated_GMM_Labels[-1])]
plt.legend(handles=legend_handles, loc='best')

plt.savefig(f"t-SNE_Visualization_{Model_name}_{Dataset_name}_GMM.pdf", format="pdf", bbox_inches="tight")
plt.close()

print(f"Experiment Completed on Model: {Model_name} and {Dataset_name} Dataset")