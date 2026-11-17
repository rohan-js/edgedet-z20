"""
train_model.py
Train a simple CNN on CIFAR-10 and export weights for FPGA

This script:
  1. Downloads CIFAR-10 dataset
  2. Trains a simple CNN matching the HLS architecture
  3. Exports weights as C header .inc files for the ZedBoard ARM app

Architecture (matches HLS exactly):
  Conv1(3→16, 3×3) + ReLU + MaxPool(2×2)
  Conv2(16→32, 3×3) + ReLU + MaxPool(2×2)
  FC(1152→10)

Usage: python train_model.py
Output: sw/weights/*.inc files
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
import numpy as np
import os

# ============================================================
# CNN Model (matches HLS architecture exactly)
# ============================================================
class SimpleCNN(nn.Module):
    """
    Simple CNN for CIFAR-10 classification.
    Architecture matches the HLS accelerator dimensions exactly.
    """
    def __init__(self, num_classes=10):
        super(SimpleCNN, self).__init__()
        
        # Conv1: 3 → 16 channels, 3×3 kernel
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=0, bias=True)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool2d(2, 2)
        
        # Conv2: 16 → 32 channels, 3×3 kernel
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=0, bias=True)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool2d(2, 2)
        
        # FC: 32*6*6 = 1152 → 10 classes
        self.fc = nn.Linear(32 * 6 * 6, num_classes, bias=True)
    
    def forward(self, x):
        # x: [batch, 3, 32, 32]
        x = self.pool1(self.relu1(self.conv1(x)))  # → [batch, 16, 15, 15]
        x = self.pool2(self.relu2(self.conv2(x)))   # → [batch, 32, 6, 6]
        x = x.view(x.size(0), -1)                   # → [batch, 1152]
        x = self.fc(x)                               # → [batch, 10]
        return x


# ============================================================
# Training
# ============================================================
def train_model(epochs=20, batch_size=64, lr=0.001):
    """Train the CNN on CIFAR-10."""
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Using device: {device}")
    
    # Data augmentation and normalization
    transform_train = transforms.Compose([
        transforms.RandomHorizontalFlip(),
        transforms.RandomCrop(32, padding=4),
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), 
                           (0.2470, 0.2435, 0.2616))
    ])
    
    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465),
                           (0.2470, 0.2435, 0.2616))
    ])
    
    # Download CIFAR-10
    print("[INFO] Downloading CIFAR-10 dataset...")
    trainset = torchvision.datasets.CIFAR10(
        root='./data', train=True, download=True, transform=transform_train)
    trainloader = torch.utils.data.DataLoader(
        trainset, batch_size=batch_size, shuffle=True, num_workers=2)
    
    testset = torchvision.datasets.CIFAR10(
        root='./data', train=False, download=True, transform=transform_test)
    testloader = torch.utils.data.DataLoader(
        testset, batch_size=batch_size, shuffle=False, num_workers=2)
    
    # Create model
    model = SimpleCNN(num_classes=10).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)
    
    print(f"\n[INFO] Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"[INFO] Training for {epochs} epochs...\n")
    
    # Training loop
    best_acc = 0
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for i, (inputs, labels) in enumerate(trainloader):
            inputs, labels = inputs.to(device), labels.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
        
        train_acc = 100. * correct / total
        scheduler.step()
        
        # Evaluate on test set
        model.eval()
        test_correct = 0
        test_total = 0
        with torch.no_grad():
            for inputs, labels in testloader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                _, predicted = outputs.max(1)
                test_total += labels.size(0)
                test_correct += predicted.eq(labels).sum().item()
        
        test_acc = 100. * test_correct / test_total
        
        print(f"  Epoch [{epoch+1:2d}/{epochs}]  "
              f"Loss: {running_loss/len(trainloader):.4f}  "
              f"Train Acc: {train_acc:.1f}%  "
              f"Test Acc: {test_acc:.1f}%")
        
        if test_acc > best_acc:
            best_acc = test_acc
            torch.save(model.state_dict(), 'best_model.pth')
    
    print(f"\n[RESULT] Best test accuracy: {best_acc:.1f}%")
    return model


# ============================================================
# Export Weights as C Header Files
# ============================================================
def export_weights(model, output_dir="../sw/weights"):
    """Export trained weights as .inc files for C compilation."""
    
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[INFO] Exporting weights to {output_dir}/")
    
    weights = {
        'conv1_weights': model.conv1.weight.data.cpu().numpy().flatten(),
        'conv1_bias':    model.conv1.bias.data.cpu().numpy().flatten(),
        'conv2_weights': model.conv2.weight.data.cpu().numpy().flatten(),
        'conv2_bias':    model.conv2.bias.data.cpu().numpy().flatten(),
        'fc_weights':    model.fc.weight.data.cpu().numpy().flatten(),
        'fc_bias':       model.fc.bias.data.cpu().numpy().flatten(),
    }
    
    for name, data in weights.items():
        filepath = os.path.join(output_dir, f"{name}.inc")
        with open(filepath, 'w') as f:
            # Write as comma-separated float values
            values = ", ".join([f"{v:.8f}" for v in data])
            f.write(values + "\n")
        
        print(f"  {name}.inc: {len(data)} values "
              f"(range: [{data.min():.4f}, {data.max():.4f}])")
    
    # Also save as numpy arrays for Python testing
    np.savez(os.path.join(output_dir, 'weights.npz'), **weights)
    print(f"  weights.npz: saved for Python testing")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  CNN Training for ZedBoard FPGA Accelerator")
    print("=" * 50)
    
    # Train the model
    model = train_model(epochs=20, batch_size=64, lr=0.001)
    
    # Load best checkpoint
    model.load_state_dict(torch.load('best_model.pth'))
    
    # Export weights for FPGA
    export_weights(model)
    
    print("\n" + "=" * 50)
    print("  Training Complete!")
    print("  Next: Copy .inc files to sw/src/ and rebuild")
    print("=" * 50)
