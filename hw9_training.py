

#Import the necessary modules for the job
import time
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
            labels += [i for j in range(1500)]  #Append labels based on how data was loaded
        self.labels = labels
    def __len__(self):
        # Return the total number of images
        return len(self.dataset)
    def __getitem__(self, index):
        img = Image.open(self.dataset[index])
        img_tensor = tvt.ToTensor()(img) #Convert Image to tensors (C x H x W)
        #Ensure all images possess same channels (changing 1 channel images to 3)
        if img_tensor.size()[0] == 1:
            img_tensor = img_tensor.repeat(3, 1, 1)
        # Apply transformations to the image
        transform1 = tvt.RandomAffine(degrees = 30, translate = (0.2, 0.2))
        transform2 = tvt.ColorJitter(brightness = (0.7, 1), saturation = (0.5, 1), contrast = (0.4, 1))
        transform3 = tvt.RandomHorizontalFlip()
        transform = tvt.Compose([transform1, transform2, transform3])
        # Transform the non-oblique image
        trans_tensor = transform(img_tensor)
        int_label = self.labels[index]
        # Return the tuple: (augmented tensor, integer label)
        return trans_tensor, int_label

#Function to create dataset given list
def dataset_appender(dataset, imgIds, coco):
    for entry in range(len(imgIds)):    #Entry is an integer index
        # print(f"Round {entry+1} of {len(imgIds)}")
        img = coco.loadImgs(imgIds[entry])[0]  #img here is a dictionary
        I = os.path.join('train2014', img['file_name']) #Pass full path to the image file when appending to dataset 
        dataset.append(I)
    return dataset

#Data Creator function (Dataset of 5 classes)
def datacreator():
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


    # get all images containing given categories
    categories_list = ['airplane', 'bus', 'cat', 'dog', 'pizza']
    dataset = []    #Initializing an empty dataset
    os.chdir('train2014/')
    for k in range(len(categories_list)):
        catIds = coco.getCatIds(catNms=categories_list[k]);
        imgIds = coco.getImgIds(catIds=catIds ); #Initializing imgIds as a list
        imgIds = imgIds[0:1500] #1500 training images for each category
        dataset = dataset_appender(dataset, imgIds, coco)

    # print(len(dataset)) #Dataset should contain 10000 images given the 2014train dataset
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

#The training function
def training(net1, mydataloader, device):
    net = net1.to(device)
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        net.parameters(), lr = 1e-3, betas = (0.9, 0.99)  #Learning rate here
        )
    epochs = 15 #Number of epochs
    #Initialize loss graph
    loss_graph = []
    #Initialize iterations
    iteration = 0
    iterations = []
    for epoch in range(epochs):
        running_loss = 0.0
        # For loop for mydataloader to process 7500 images (since each class has around 2000)
        for count, batch in enumerate(mydataloader):
            # print(f"{count+1} out of {int(7500/mydataloader.batch_size)} iterations complete")
            inputs, labels = batch
            inputs = inputs.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            outputs = net(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

            if (count+1) % 10 == 0:
                print("[epoch: %d, batch: %5d] loss: %.3f"  % (epoch+1, count+1, running_loss/100))
                loss_graph.append(running_loss/100)   #Appending loss onto a list for graphing 
                running_loss = 0.0
                iterations.append(iteration)    #Appending number of iterations passed
                iteration += 1
    return loss_graph, iterations, net


#Method for evaluating the confusion matrix
def confusionmatrix(net, mydataloader, device, path):
    #Set network to evaluation mode
    net = net.eval()
    correct = 0
    total = 0
    y_pred = []
    y = []
    # with torch.no_grad():
    for data in mydataloader:
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
            y_pred.append(prediction) # list of predicted labels
            y.append(label) # list of true labels
    # print(y)
    print('Accuracy of the network on the test images: %d %%' % (100* correct/total))
    cf_matrix = confusion_matrix(y, y_pred) # create the confusion matrix
    sns_plot = sns.heatmap(cf_matrix, annot=True, fmt='g', cbar=False) # use heatmap to demonstrate the confusion matrix
    fig = sns_plot.get_figure()
    #Saving the figure
    plt.savefig(os.path.join(path, "confusion_matrix_ViT.jpg"))
    
    plt.show()

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

#Making sure that the images have been resized into 64x64
def image_size():
  #Alter the images that are not in 64x64
  target_size = (64, 64)
  os.chdir("/content/drive/MyDrive/Purdue-First Year/BME 64600/hw9_RussellHo/train2014")
  image_count = 1
  for image_name in os.listdir():
    print(f"Altering {image_count} of {len(os.listdir())} images")
    if image_name.lower().endswith(".jpg"):
      image = Image.open(image_name)
      if image.size != target_size:
        new_image = image.resize(target_size)
        new_image.save(image_name)
        print("Resizing completed for one image")
    image_count += 1
  

#Main Script
def main():
  #Obtain 5 classes through datacreator ('airplane', 'bus', 'cat', 'dog', 'pizza')
  dataset = datacreator() #directory changed into train2014 here

  #Creating an instance from the dataloader class
  my_dataset = MyDataset(dataset)
  # Wrapping the Dataset within the DataLoader class
  mydataloader = DataLoader(my_dataset, shuffle = True, batch_size = 100, num_workers = 1)

  # os.chdir("train2014")

  #First check if CUDA is available
  use_cuda = torch.cuda.is_available()
  print("Is CUDA computing available? " + str(use_cuda))
  device = torch.device("cuda:0"if use_cuda else "cpu")

  #Create instance from Vision Transformer class
  vit_model = ViT(image_size=64, patch_size=16, num_channels=3, num_classes=5, embedding_size=256, num_heads=8, num_layers=6)
  loss_graph, iterations, vit_model = training(vit_model, mydataloader, device)

  #Saving the trained model
  torch.save(vit_model.state_dict(), "vit_model.pth")

  #Plot out the graph for loss
  plt.plot(iterations, loss_graph)
  plt.xlabel("Iterations")
  plt.ylabel("Loss")
  plt.title("Training Loss vs Iterations Vision Transformer")
  #Saving the training loss plot
  path = "/content/drive/MyDrive/Purdue-First Year/BME 64600/hw9_RussellHo"
  plt.savefig(os.path.join(path, "ViT_train_loss.jpg"))
  plt.show()

if __name__ == "__main__":
  # image_size()
  main()