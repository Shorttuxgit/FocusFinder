import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Image(systemName: "globe")
                .imageScale(.small)
                .foregroundStyle(.tint)
            Text("Placeholder")
                .font(.title)
                .foregroundColor(.blue)
                .bold()
            Text("Placeholder")
                .font(.title2)
                .foregroundColor(.green)
        }
        .padding()
    }
}