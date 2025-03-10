
#Import the necessary modules for the job
from pycocotools.coco import COCO
import numpy as np
import matplotlib.pyplot as plt
import skimage.io as io
from PIL import Image
from torchvision import utils
from torch.utils.data import DataLoader
import os
import torch
from PIL import Image
from torchvision import transforms as tvt
import torch.nn as nn
from sklearn.metrics import confusion_matrix
import seaborn as sns
import torch.nn.functional as F
#Import the ViTHelper.py file
os.chdir("/content/drive/MyDrive/Purdue-First Year/BME 64600/hw9_RussellHo/")
from ViTHelper import MasterEncoder, SelfAttention, AttentionHead

#Class for Dataloader (found in hw4)
class MyDataset(torch.utils.data.Dataset):
    def __init__(self, dataset):
        super().__init__()
        self.dataset = dataset
        labels = []
        for i in range(5):
            labels += [i for j in range(500)]  #Append labels based on how data was loaded, in this case there are 500 validation images in each class
        self.labels = labels
    def __len__(self):
        # Return the total number of images
        return len(self.dataset)
    def __getitem__(self, index):
      try:
        img = Image.open(self.dataset[index])
      except OSError as e:
        print(f"Error opening file: {self.dataset[index]}")
        print(f"Error message: {e}")
        raise
      img_tensor = tvt.ToTensor()(img) #Convert Image to tensors (C x H x W)
      #Ensure all images possess same channels (changing 1 channel images to 3)
      if img_tensor.size()[0] == 1:
          img_tensor = img_tensor.repeat(3, 1, 1)

      int_label = self.labels[index]
      # Return the tuple: (augmented tensor, integer label)
      return img_tensor, int_label

#Function to create dataset given list
def dataset_appender(dataset, imgIds, coco):
    for entry in range(len(imgIds)):    #Entry is an integer index
        # print(f"Round {entry+1} of {len(imgIds)}")
        img = coco.loadImgs(imgIds[entry])[0]  #img here is a dictionary
        I = os.path.join('train2014', img['file_name']) #Pass full path to the image file when appending to dataset 
        dataset.append(I)
    return dataset

#Data Creator function (Dataset of 5 classes)
def test_datacreator():
    #Section for initializing COCO API for instance annotations
    os.chdir("/content/drive/MyDrive/Purdue-First Year/BME 64600/hw9_RussellHo")
    # print(os.listdir())
    dataType = 'train2014'
    annFile = 'annotations/instances_{}.json'.format(dataType)
    # initialize COCO api for instance annotations
    coco=COCO(annFile)

    # # display COCO categories and supercategories
    # cats = coco.loadCats(coco.getCatIds())
    # nms=[cat['name'] for cat in cats]
    # print('COCO categories: \n{}\n'.format(' '.join(nms)))

    # nms = set([cat['supercategory'] for cat in cats])
    # print('COCO supercategories: \n{}'.format(' '.join(nms)))


    # get test images containing given categories
    categories_list = ['airplane', 'bus', 'cat', 'dog', 'pizza']
    dataset = []    #Initializing an empty dataset
    os.chdir('train2014/')
    for k in range(len(categories_list)):
        catIds = coco.getCatIds(catNms=categories_list[k]);
        imgIds = coco.getImgIds(catIds=catIds ); #Initializing imgIds as a list
        imgIds = imgIds[0:500] #500 images for each category in test
        dataset = dataset_appender(dataset, imgIds, coco)

    # print(len(dataset)) #Dataset should contain 10000 images given the 2014 test dataset
    # #For loop for iterating over the 3 images in the given class
    # list_images = []
    # for j in range(3):
    #     img = Image.open(dataset[np.random.randint(0,len(dataset))])    #Selecting an image belonging to one of the categories at random
    #     list_images.append(img)
    # f, axarr = plt.subplots(1, 3)
    # axarr[0].imshow(list_images[0])
    # plt.axis('off')
    # axarr[1].imshow(list_images[1])
    # plt.axis('off')
    # axarr[2].imshow(list_images[2])
    # plt.axis('off')
    # plt.show()

    # #Loading a random image from the dataset
    # img = Image.open(dataset[np.random.randint(0,len(dataset))])
    # img.show()
    os.chdir("../")
    return dataset

class ViT(nn.Module):
    def __init__(self, image_size, patch_size, num_channels, num_classes, embedding_size, num_heads, num_layers):
        super().__init__()
        
        # Calculate the number of patches and the max sequence length
        num_patches = (image_size // patch_size) ** 2
        seq_length = num_patches + 1 
        
        #Conv2D layer for embedding patches (use kernel size and stride to apply layer onto image without dividing into patches)
        self.embedding_conv = nn.Conv2d(num_channels, embedding_size, kernel_size=patch_size, stride=patch_size)

        #Initialize class token as a learnable parameter
        self.class_token = nn.Parameter(torch.randn(1, 1, embedding_size))

        # Setting position embeddings as learnable parameters
        self.position_embeddings = nn.Parameter(torch.randn(1, seq_length, embedding_size)) #Dimensions (1, seq_length, embedding_size)

        # Transformer encoder
        self.encoder = MasterEncoder(seq_length, embedding_size, num_layers, num_heads)

        # Final class prediction using the class token and an MLP layer
        self.mlp = nn.Linear(embedding_size, num_classes) #Outputs class logits

    def forward(self, x):
        # Create embeddings using the Conv2D layer
        embeddings = self.embedding_conv(x) #First apply Conv2D layer on input image (x) 
        embeddings = embeddings.view(embeddings.shape[0], -1, embeddings.shape[1]) #Reshape output tensor to have dimensions (batch_size, num_patches, embedding_size)

        #Add class token to the sequence
        batch_size = x.shape[0]
        class_tokens = self.class_token.expand(batch_size, -1, -1)  #Expand class token to match batch size
        embeddings_with_token = torch.cat([class_tokens, embeddings], dim=1)  #add class token to sequence

        # Add position embeddings to sequence of embeddings with class token
        embeddings_with_token_and_positions = embeddings_with_token + self.position_embeddings

        # Pass through the Transformer encoder
        transformer_output = self.encoder(embeddings_with_token_and_positions)

        #Take the class token (extracted from the transformer's output sequence) and feed it through the MLP
        class_token_output = transformer_output[:, 0]
        logits = self.mlp(class_token_output) #Produces final Logits

        return logits

#Method for evaluating the confusion matrix
def confusionmatrix(net, mydataloader, device, path):
    #Set network to evaluation mode
    net = net.eval()
    correct = 0
    total = 0
    y_pred = []
    y = []
    with torch.no_grad():
      for i, data in enumerate(mydataloader):
        print(f"Processing batch {i+1}...")
        images, labels = data   #Acquiring image tensors and their respective labels from dataloader
        images = images.to(device)
        labels = labels.to(device)
        outputs = net(images)
        _, predicted = torch.max(outputs.data, 1)   #Only interested in the labels of the predicted images
        total += labels.size(0)
        correct += (predicted == labels).sum().item()
        # print(predicted)
        # print(labels)
        for label,prediction in zip(labels,predicted):
            y_pred.append(prediction.cpu()) # list of predicted labels
            y.append(label.cpu()) # list of true labels (move to cpu) then append to list
    # print(y)
    print('Accuracy of the network on the test images: %d %%' % (100* correct/total))
    cf_matrix = confusion_matrix(y, y_pred) # create the confusion matrix
    sns_plot = sns.heatmap(cf_matrix, annot=True, fmt='g', cbar=False) # use heatmap to demonstrate the confusion matrix
    fig = sns_plot.get_figure()
    #Saving the figure
    plt.savefig(os.path.join(path, "confusion_matrix_ViT.jpg"))
    plt.show()

if __name__ == "__main__":
  #Create the test dataset (from validation images)
  test_dataset = test_datacreator()
  #Create an instance from the dataloader class for the test dataset
  test_my_dataset = MyDataset(test_dataset)
  #Wrap the test Dataset within the DataLoader class
  test_mydataloader = DataLoader(test_my_dataset, shuffle = True, batch_size = 100, num_workers = 1)

  #Loading the model for evaluation on test dataset
  vit_model = ViT(image_size=64, patch_size=16, num_channels=3, num_classes=5, embedding_size=256, num_heads=8, num_layers=6)
  vit_model.load_state_dict(torch.load("vit_model.pth"))

  #First check if CUDA is available
  use_cuda = torch.cuda.is_available()
  print("Is CUDA computing available? " + str(use_cuda))
  device = torch.device("cuda:0"if use_cuda else "cpu")

  # Move the model to the GPU
  vit_model = vit_model.to(device)

  #Evaluate the model on the test data using the confusion matrix function
  confusionmatrix(vit_model, test_mydataloader, device, "/content/drive/MyDrive/Purdue-First Year/BME 64600/hw9_RussellHo")