import matplotlib.pyplot as plt
import torch
from torch import nn, optim
from torchvision import datasets, models, transforms
from torch.utils.data import DataLoader
from collections import OrderedDict
from PIL import Image
import argparse

# Define Mandatory and Optional Arguments for the script
def arg_parser():
    parser = argparse.ArgumentParser(description="Train.py")
    parser.add_argument('--data_dir', help='Provide data directory. Mandatory argument', default="flowers", type=str)
    parser.add_argument('--arch', dest="arch", action="store", default="vgg19", type=str)
    parser.add_argument('--save_dir', dest="save_dir", action="store", default="./checkpoint.pth")
    parser.add_argument('--learning_rate', dest="learning_rate", action="store", default=0.001, type=float)
    parser.add_argument('--hidden_units', type=int, dest="hidden_units", action="store", default=120)
    parser.add_argument('--epochs', dest="epochs", action="store", type=int, default=10)
    parser.add_argument('--gpu', dest="gpu", action="store", default="gpu")
    args = parser.parse_args()
    return args

# Transforming functions for the training, validation, and testing sets
def train_transformer(train_dir):
    train_transforms = transforms.Compose([
        transforms.RandomRotation(30),
        transforms.RandomResizedCrop(224),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    train_data = datasets.ImageFolder(train_dir, transform=train_transforms)
    return train_data

def test_transformer(test_dir):
    test_transforms = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    test_data = datasets.ImageFolder(test_dir, transform=test_transforms)
    return test_data

def valid_transformer(valid_dir):
    valid_transforms = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    valid_data = datasets.ImageFolder(valid_dir, transform=valid_transforms)
    return valid_data

# Checking for GPU availability
def check_gpu(gpu_arg):
    if not gpu_arg:
        return torch.device("cpu")    
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    return device

# Using the image datasets and the transforms, define the dataloaders
def data_loader(data, train=True):
    loader = DataLoader(data, batch_size=64, shuffle=train)
    return loader

# Creating a function for the classifier
def initial_classifier(model, input_feat, hidden_units_1=1000, hidden_units_2=500, hidden_units_3=204):
    classifier = nn.Sequential(OrderedDict([
        ('fc1', nn.Linear(input_feat, hidden_units_1)),
        ('relu1', nn.ReLU()),
        ('dropout1', nn.Dropout(p=0.5)),
        ('fc2', nn.Linear(hidden_units_1, hidden_units_2)),
        ('relu2', nn.ReLU()),
        ('dropout2', nn.Dropout(p=0.5)),
        ('fc3', nn.Linear(hidden_units_2, hidden_units_3)),
        ('relu3', nn.ReLU()),
        ('dropout3', nn.Dropout(p=0.5)),
        ('fc4', nn.Linear(hidden_units_3, 102)),
        ('output', nn.LogSoftmax(dim=1))
    ]))
    model.classifier = classifier
    return classifier

# Defining a model for transfer learning
def primaryloader_model(architecture="vgg19"):
    if architecture.startswith('vgg'):
        model = models.vgg19(pretrained=True)
        model.name = "vgg19"
        input_feat = 25088
    elif architecture.startswith('dense'):
        model = models.densenet121(pretrained=True) 
        input_feat = 1024
    elif architecture.startswith('alex'):
        model = models.alexnet(pretrained=True) 
        input_feat = 9216
    for param in model.parameters():
        param.requires_grad = False
    return model, input_feat

# Training the model on custom datasets
def network_trainer(model, train_loader, valid_loader, device, criterion, optimizer, epochs, print_every, steps):
    print("Training starting .....\n")
    # Train Model
    running_loss = 0
    for epoch in range(epochs):
        for inputs, labels in train_loader:
            steps += 1
            inputs, labels = inputs.to(device), labels.to(device)
            logps = model.forward(inputs)
            loss = criterion(logps, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            if steps % print_every == 0:
                valid_loss = 0
                accuracy = 0
                model.eval()
                with torch.no_grad():
                    for inputs, labels in valid_loader:
                        inputs, labels = inputs.to(device), labels.to(device)
                        logps = model.forward(inputs)
                        batch_loss = criterion(logps, labels)
                        valid_loss += batch_loss.item()
                        ps = torch.exp(logps)
                        top_p, top_class = ps.topk(1, dim=1)
                        equals = top_class == labels.view(*top_class.shape)
                        accuracy += torch.mean(equals.type(torch.FloatTensor)).item()
                print(f"Epoch {epoch+1}/{epochs}.. "
                      f"Train loss: {running_loss/print_every:.3f}.. "
                      f"Valid loss: {valid_loss/len(valid_loader):.3f}.. "
                      f"Valid accuracy: {accuracy/len(valid_loader)*100:.3f}")
                running_loss = 0
                model.train()
    return model

# Testing your network
def validate_model(model, test_loader, device):
    correct, total = 0, 0
    with torch.no_grad():
        model.eval()
        for images, labels in test_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    print('Accuracy on test images is: %d%%' % (100 * correct / total))

# Saving the trained model for future purposes
def initial_checkpoint(model, save_dir, train_data, arch):    
    model.to('cpu')
    model.class_to_idx = train_data.class_to_idx 
    checkpoint = {
        'dropout': 0.4,
        'epochs': 12,
        'classifier': model.classifier,
        'state_dict': model.state_dict(),
        'mapping': model.class_to_idx,
        'architecture': arch,
    }        
    torch.save(checkpoint, save_dir)

# Get Keyword Args for Training
args = arg_parser()

# Set directory for training
data_dir = args.data_dir
train_dir = data_dir + '/train'
valid_dir = data_dir + '/valid'
test_dir = data_dir + '/test'

# Pass transforms in, then create trainloader
train_data = train_transformer(train_dir)
test_data = test_transformer(test_dir)
valid_data = valid_transformer(valid_dir)

trainloader = data_loader(train_data)
validloader = data_loader(valid_data, False)
testloader = data_loader(test_data, False)

model, input_feat = primaryloader_model(args.arch)
model.classifier = initial_classifier(model, input_feat)

# Checking for device
device = check_gpu(gpu_arg=args.gpu)
model.to(device)

# Setting up learning rate
learning_rate = args.learning_rate
criterion = nn.NLLLoss()
optimizer = optim.Adam(model.classifier.parameters(), lr=learning_rate)

# Initializing the variable   
print_every = 50
steps = 0

# Training the model
trained_model = network_trainer(model, trainloader, validloader, device, criterion, optimizer, args.epochs, print_every, steps)
print("\nTraining completed!!")

# Checking the testing accuracy    
validate_model(trained_model, testloader, device)
initial_checkpoint(trained_model, args.save_dir, train_data, args.arch)
